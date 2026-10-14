<#
.SYNOPSIS
  Supervision Uvicorn RestoIA (D1.28) : lance server:app et consigne dans le journal de vie
  le demarrage et la fin reels du processus supervise (pas du shell qui l'a lance).
  Aucun redemarrage automatique. Aucun secret ni valeur de connexion journalise.
  Aucun processus preexistant n'est jamais arrete.

  Determination de l'interpreteur (direct uniquement) :
    1) parametre -PythonExe (chemin direct vers python.exe) ;
    2) python.exe de la PATH (stub WindowsApps ignore).
  Chaque candidat est valide par une sonde "import uvicorn, fastapi, motor, dotenv"
  (interpreteur execute brievement, sans demarrer l'application). Si aucun candidat
  ne passe la sonde, le script s'arrete avant tout lancement (code 6).
  Le retenu est lance directement avec "-m uvicorn server:app" et son handle
  -PassTru sert de supervision.

  Protection d'environnement : server.py:5 charge .env via load_dotenv sans
  override (une variable deja presente dans l'environnement du processus gagne
  sur .env) et database.py:4-5 construit le client MONGO_URL/DB_NAME a l'import.
  Le wrapper exige donc, avant tout lancement, que MONGO_URL et DB_NAME soient
  deja renseignees (non vides) dans l'environnement ET que MONGO_URL cible une
  adresse loopback : les parametres Atlas du .env ne peuvent pas etre engages
  accidentellement. Valeurs jamais journalisees.

  Codes de sortie :
    1 = parametre invalide, 2 = port deja en ecoute, 3 = echec d'identification ou
    de lancement (voir journal), 4 = verification du port impossible, 5 = journal
    de vie inaccessible, 6 = interpreteur non determinable, 7 = Start-Process echoue,
    8 = protection de l'environnement refusee (MONGO_URL/DB_NAME).
#>
param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8001,
    [string]$LifeLog = "_server_life.log",
    [string]$PythonExe = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Port -lt 1 -or $Port -gt 65535) {
    Write-Host "Parametre -Port invalide ($Port)."; exit 1
}

# --- 1. Determination et validation de l'interpreteur (aucune application demarree)
$candidates = New-Object System.Collections.ArrayList
if ($PythonExe -ne "") {
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Write-Host "Securite : -PythonExe introuvable ($PythonExe) - arret avant tout lancement."
        exit 6
    }
    [void]$candidates.Add($PythonExe)
}
try { $pc = Get-Command python.exe -ErrorAction Stop } catch { $pc = $null }
if ($pc -and $pc.Source -notmatch 'WindowsApps') {
    [void]$candidates.Add($pc.Source)
}
$chosen = $null
foreach ($exePath in $candidates) {
    try {
        & $exePath -c "import uvicorn, fastapi, motor, dotenv" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $chosen = $exePath; break }
    } catch { }
}
if (-not $chosen) {
    Write-Host "Securite : aucun interpreteur direct valide (-PythonExe ou python.exe de la PATH) - arret avant tout lancement (code 6)."
    exit 6
}
Write-Host "Interpreteur retenu : $chosen"

# --- 1bis. Protection de l'environnement (isolation vs .env Atlas)
# Garantie mecanique : le .env charge par le fils via load_dotenv (override=False
# par defaut) ne remplacera PAS MONGO_URL/DB_NAME deja presents dans l'environnement
# herite. On refuse tout lancement si ces variables sont absentes/vides (sinon le
# .env serait la seule source possible) ou si MONGO_URL ne vise pas une boucle
# locale. Comportement d'une URI vide dans AsyncIOMotorClient n'etant pas verifiable
# ici (aucun processus applicatif), la conception ne s'appuie jamais dessus.
$mongoUrl = [Environment]::GetEnvironmentVariable("MONGO_URL")
$dbName   = [Environment]::GetEnvironmentVariable("DB_NAME")
if ([string]::IsNullOrWhiteSpace($mongoUrl) -or [string]::IsNullOrWhiteSpace($dbName)) {
    Write-Host "Securite : MONGO_URL et DB_NAME doivent etre deja renseignees (non vides) dans l'environnement - sinon le .env ferait seule source. Aucun lancement (code 8)."
    exit 8
}
if ($mongoUrl -cnotmatch '^mongodb://') {
    Write-Host "Securite : schema MONGO_URL non prevu (attendu exactement mongodb:// ; valeur et identifiants non affiches) - aucun lancement (code 8)."
    exit 8
}
$mongoHost = $null
try {
    $mongoUri = New-Object System.Uri($mongoUrl)
    if (-not $mongoUri.IsAbsoluteUri) { throw "URI non absolue" }
    $mongoHost = $mongoUri.Host
} catch { $mongoHost = $null }
# Note IPv6 : sur PowerShell 5.1/.NET Framework, System.Uri peut normaliser ::1
# en forme complete ([0000:...:0001]) qui tombe hors liste blanche -> refus
# conservateur (fail-safe) volontairement conserve, sans logique IPv6 ajoutee.
if (-not $mongoHost -or $mongoHost -cnotin @("localhost", "127.0.0.1", "::1", "[::1]")) {
    Write-Host "Securite : hote MONGO_URL pas exactement une boucle locale (valeur non affichee) - forme malformee, non prevue ou ambigue refusee ; aucun lancement (code 8)."
    exit 8
}
Write-Host "Environnement : MONGO_URL loopback et DB_NAME renseignes (valeurs jamais journalisees)."

# --- 2. Verification du port : conservatrice, sans texte d'exception localise
# Interrogation CIM directe (meme donnee que Get-NetTCPConnection) : une collection
# vide retournee normalement prouve l'absence d'ecoute ; toute exception = echec
# de la verification -> arret par precaution.
$portState = $null   # "libre" | "occupe" | "impossible"
$listeners = @()
try {
    $null = Get-Command Get-CimInstance -ErrorAction Stop
} catch {
    $portState = "impossible"
}
if ($null -eq $portState) {
    try {
        $listeners = @(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection `
            -Filter "State = 2 AND LocalPort = $Port" -ErrorAction Stop)
        $portState = if ($listeners.Count -gt 0) { "occupe" } else { "libre" }
    } catch {
        $portState = "impossible"
    }
}
if ($portState -eq "impossible") {
    Write-Host "Securite : verification du port $Port impossible ou echouee - arret par precaution (code 4)."
    exit 4
}
if ($portState -eq "occupe") {
    Write-Host "Port $BindHost`:$Port deja en ecoute ($($listeners.Count) ouverture(s)) - aucun demarrage lance (code 2)."
    exit 2
}
Write-Host "Port $Port : aucun processus en ecoute (verification reussie)."

# --- 3. Journal de vie : resolution des chemins relatif/absolu + test d'ecriture
if ([System.IO.Path]::IsPathRooted($LifeLog)) {
    $lifePath = $LifeLog
} else {
    $lifePath = Join-Path $PSScriptRoot $LifeLog
}
$lifePath = [System.IO.Path]::GetFullPath($lifePath)
try {
    $dir = Split-Path -Parent $lifePath
    if (-not (Test-Path -LiteralPath $dir)) { throw "dossier introuvable : $dir" }
    [System.IO.File]::AppendAllText($lifePath, "")
} catch {
    Write-Host "Securite : journal de vie inaccessible ($lifePath) - arret sans lancer de processus (code 5). Detail : $($_.Exception.Message)"
    exit 5
}

$stamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$outLog = Join-Path $PSScriptRoot "_server_live_$stamp.log"
$errLog = Join-Path $PSScriptRoot "_server_live_${stamp}_err.log"

# --- 4. Lancement direct de l'interpreteur (env du processus heritee, jamais journalisee)
try {
    $serverProc = Start-Process -FilePath $chosen `
        -ArgumentList @("-m","uvicorn","server:app","--host",$BindHost,"--port",$Port) `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
} catch {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ECHEC port=$Port - Start-Process echoue : $($_.Exception.Message)"
    try { Add-Content -LiteralPath $lifePath -Value $line } catch { }
    Write-Host "Echec du lancement Start-Process (code 7). Detail : $($_.Exception.Message)"
    exit 7
}

# --- 5. Ligne DEMARRAGE (echec d'ecriture : supervision maintenue malgre tout)
try {
    Add-Content -LiteralPath $lifePath -Value ("$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') DEMARRAGE host=$BindHost port=$Port pid_supervise=$($serverProc.Id) logs=$([System.IO.Path]::GetFileName($outLog))")
} catch {
    Write-Host "Avertissement : ecriture DEMARRAGE impossible ; supervision maintenue. Detail : $($_.Exception.Message)"
}
Write-Host "Processus supervise : PID $($serverProc.Id) - journal de vie $lifePath"

# --- 6. Attente du handle retourne par Start-Process + enregistrement factuel de la fin
$started = Get-Date
try {
    $serverProc.WaitForExit()
    $exitCode = try { "$($serverProc.ExitCode)" } catch { "indisponible" }
} catch {
    # Handle perdu avant l'attachement : fait consigne tel quel, aucune interpretation.
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') FIN pid_supervise=$($serverProc.Id) exit_code=indisponible duree=00:00:00 cause_notee=handle_perdu_avant_supervision"
    try { Add-Content -LiteralPath $lifePath -Value $line } catch { Write-Host "Avertissement : journal FIN non ecrit : $line" }
    Write-Host "Termine : handle perdu avant supervision, code de sortie indisponible."
    exit 3
}
$duree = (Get-Date) - $started
# Fait brut uniquement : aucun interpretation du code (0 n'est pas une preuve
# d'arret volontaire ; l'absence de ligne FIN signale la mort du wrapper lui-meme).
$line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') FIN pid_supervise=$($serverProc.Id) exit_code=$exitCode duree=$($duree.ToString('d\.hh\:mm\:ss'))"
try {
    Add-Content -LiteralPath $lifePath -Value $line
} catch {
    Write-Host "Avertissement : journal FIN non ecrit : $line"
}
Write-Host "Termine : code de sortie $exitCode (fait consigne, sans interpretation)."
