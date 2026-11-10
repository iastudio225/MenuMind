<#
.SYNOPSIS
  Supervision Uvicorn MenuMind (D1.28) : lance server:app et consigne dans le journal de vie
  le demarrage et la fin reels du processus supervise (pas du shell qui l'a lance).
  Aucun redemarrage automatique. Aucun secret ni valeur de connexion journalise.
  Aucun processus preexistant n'est jamais arrete.

  Determination de l'interpreteur (direct uniquement) :
    1) parametre -PythonExe (chemin direct vers python.exe) ;
    2) python.exe de la PATH (stub WindowsApps ignore).
  Chaque candidat est valide par une sonde "import uvicorn, fastapi, asyncpg, dotenv"
  (interpreteur execute brievement, sans demarrer l'application). Si aucun candidat
  ne passe la sonde, le script s'arrete avant tout lancement (code 6).
  Le retenu est lance directement avec "-m uvicorn server:app" et son handle
  -PassTru sert de supervision.

  Protection d'environnement : server.py charge .env sans override, donc
  SUPABASE_DB_URL doit etre injectee dans l'environnement avant le lancement.
  Seul le schema PostgreSQL est accepte. La valeur n'est jamais journalisee.

  Codes de sortie :
    1 = parametre invalide, 2 = port deja en ecoute, 3 = echec d'identification ou
    de lancement (voir journal), 4 = verification du port impossible, 5 = journal
    de vie inaccessible, 6 = interpreteur non determinable, 7 = Start-Process echoue,
    8 = protection de l'environnement refusee (SUPABASE_DB_URL).
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
        & $exePath -c "import uvicorn, fastapi, asyncpg, dotenv" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $chosen = $exePath; break }
    } catch { }
}
if (-not $chosen) {
    Write-Host "Securite : aucun interpreteur direct valide (-PythonExe ou python.exe de la PATH) - arret avant tout lancement (code 6)."
    exit 6
}
Write-Host "Interpreteur retenu : $chosen"

# --- 1bis. Require explicit PostgreSQL connection injection.
# load_dotenv does not override environment variables, so a local .env alone
# must not silently select the database used by this launcher.
$postgresUrl = [Environment]::GetEnvironmentVariable("SUPABASE_DB_URL")
if ([string]::IsNullOrWhiteSpace($postgresUrl)) {
    Write-Host "Securite : SUPABASE_DB_URL doit etre defini dans l'environnement avant lancement. Aucun lancement (code 8)."
    exit 8
}
if ($postgresUrl -cnotmatch '^postgres(ql)?://') {
    Write-Host "Securite : URI PostgreSQL attendue dans SUPABASE_DB_URL (valeur non affichee). Aucun lancement (code 8)."
    exit 8
}
Write-Host "Environnement : connexion PostgreSQL injectee (valeur jamais journalisee)."

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
