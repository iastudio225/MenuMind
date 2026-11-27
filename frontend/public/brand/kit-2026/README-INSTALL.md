# AVENIQ — Brand Kit 2026 (installation frontend)

Référence officielle installée le **27 novembre 2026** depuis le Brand Kit fourni
(`AVENIQ_BrandKit(1).zip`). Ce dossier est la copie de travail du kit ; les
fichiers d'origine sont conservés tels quels.

## Contenu du kit

- `logos/` : logo horizontal, logo empilé, version sur fond sombre.
- `icons/` : aperçus App / Web App / favicon / iconographie.
- `palette/` : swatches PNG, `colors.json`, `palette.svg`.
- `docs/` : tokens CSS, typographie, composants de référence.
- `reference/` : planche de marque originale.
- `optimized/` : dérivés web réellement utilisés par l'application.

## Nature des assets

Les logos et icônes du kit sont des **recadrages raster d'aperçu** issus de la
planche de marque. Ce ne sont **pas** des fichiers vectoriels et ils n'ont pas
de fond transparent à la source. Aucun logo n'a été redessiné ou reconstruit en
SVG. Les dérivés ci-dessous retirent uniquement le fond d'aperçu et redimensionnent
l'image.

## Dérivés utilisés

| Fichier | Source | Transformation | Dimensions | Usage |
|---|---|---|---|---|
| `optimized/logo-horizontal-light.png` / `.webp` | `logos/logo-horizontal.png` | fond clair retiré (y compris les contre-formes), recadrage + 6 px | 303×88 | `AveniqBrand` variante `light` (landing, auth, sidebar, admin, footer) |
| `optimized/logo-horizontal-dark.png` / `.webp` | `logos/logo-dark-background.png` | fond extérieur retiré, carte navy officielle conservée, recadrage + 4 px | 330×118 | `AveniqBrand` variante `dark` (panneaux sombres) |
| `optimized/app-icon-16.png` | `icons/app-icon-512-preview.png` | tuile recadrée, coins blancs retirés, redimensionnement prémultiplié | 16×16 | favicon 16 px |
| `optimized/app-icon-32.png` | idem | idem | 32×32 | favicon 32 px |
| `optimized/app-icon-96.png` | idem | idem | 96×96 | `BrandLogo` (contexte carré) |
| `optimized/apple-touch-icon-192.png` | idem | idem, aplati sur blanc (iOS applique son masque) | 192×192 | `apple-touch-icon` |
| `public/og-aveniq-02.png` | logo light + composition | composition 1200×630, Inter, palette officielle | 1200×630 | Open Graph / Twitter |
| `public/og-default.png` | idem | copie de l'OG 2026 | 1200×630 | fallback des cartes de partage backend |

L'ancien contenu de `og-default.png` est identique à `public/og-aveniq-01.png`,
qui est conservé. Pour un rollback, il suffit de recopier ce fichier.

## Limites connues

- Les dimensions natives sont faibles (logo horizontal 315×105, icône App 155×152).
  Les dérivés ne sont pas des exports haute résolution.
- L'icône Apple 192 px est agrandie depuis l'aperçu 149×149 ; elle est acceptable
  pour un écran d'accueil mais ne remplace pas un export natif.
- Le logo OG est agrandi (303 → 430 px de large dans la composition 1200×630).
- La variante `dark` inclut volontairement la carte navy arrondie de la planche :
  sur un panneau de la même couleur, un léger écart de teinte reste visible.
- L'interface conserve Inter ; JetBrains Mono reste utilisée pour les usages techniques et numériques.

## Anciens assets conservés

Les dossiers `brand/logos/`, `brand/icons/`, `brand/optimized/`, `brand/web-assets/`,
`brand/brand-board/`, `brand/documentation/`, ainsi que `public/favicon.svg` et
`public/og-aveniq-01.png`, restent en place pour comparaison et rollback. Ils ne
sont plus référencés par les surfaces AVENIQ actives.
