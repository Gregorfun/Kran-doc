param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("patch","minor","major")]
  [string]$Bump,

  [Parameter(Mandatory=$true)]
  [string]$Notes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-CleanGit {
  $status = git status --porcelain
  if ($status) {
    Write-Host "❌ Working tree ist nicht clean. Bitte erst committen oder stagen." -ForegroundColor Red
    exit 1
  }
}

function Read-Version {
  if (-not (Test-Path "VERSION")) { "VERSION Datei fehlt." | Write-Error }
  $v = (Get-Content "VERSION" -Raw).Trim()
  if (-not ($v -match '^\d+\.\d+\.\d+$')) { "Ungültige VERSION: $v" | Write-Error }
  return $v
}

function Bump-Version([string]$v, [string]$bump) {
  $parts = $v.Split(".") | ForEach-Object { [int]$_ }
  $major = $parts[0]; $minor = $parts[1]; $patch = $parts[2]

  switch ($bump) {
    "major" { $major++; $minor=0; $patch=0 }
    "minor" { $minor++; $patch=0 }
    "patch" { $patch++ }
  }
  return "$major.$minor.$patch"
}

function Update-Readme([string]$newVersion, [string[]]$bullets) {
  if (-not (Test-Path "README.md")) { "README.md fehlt." | Write-Error }
  $readme = Get-Content "README.md" -Raw

  # Version ersetzen im Block "Aktuelle Version"
  $readme = [regex]::Replace(
    $readme,
    '(?s)(## Aktuelle Version\s*(?:\r?\n)\*\*)v?\d+\.\d+\.\d+(\*\*)',
    "## Aktuelle Version`r`n**v$newVersion`$2"
  )

  # Letzte Änderungen-Block ersetzen (bis zur nächsten Überschrift "## ")
  $newBullets = ($bullets | ForEach-Object { "- " + $_ }) -join "`r`n"
  $readme = [regex]::Replace(
    $readme,
    '(?s)(## Letzte Änderungen\s*(?:\r?\n))(.*?)(?:\r?\n){2}(## |# |\z)',
    "`$1$newBullets`r`n`r`n`$3"
  )

  Set-Content "README.md" $readme -NoNewline
}

function Update-Changelog([string]$newVersion, [string[]]$bullets) {
  if (-not (Test-Path "CHANGELOG.md")) { "CHANGELOG.md fehlt." | Write-Error }
  $cl = Get-Content "CHANGELOG.md" -Raw
  $today = (Get-Date).ToString("yyyy-MM-dd")

  # Füge neuen Release-Block direkt nach [Unreleased] ein
  $releaseBullets = ($bullets | ForEach-Object { "- " + $_ }) -join "`r`n"
  $insert = "## [$newVersion] - $today`r`n$releaseBullets`r`n`r`n"

  if (-not ($cl -match '## \[Unreleased\]')) {
    "CHANGELOG.md: Abschnitt ## [Unreleased] fehlt." | Write-Error
  }

  $cl = [regex]::Replace(
    $cl,
    '(?s)(## \[Unreleased\]\s*(?:\r?\n))',
    "`$1$insert",
    1
  )

  Set-Content "CHANGELOG.md" $cl -NoNewline
}

# --- Ablauf ---
Assert-CleanGit

$current = Read-Version
$new = Bump-Version $current $Bump

# Notes → Bulletpoints: entweder "|" getrennt oder Zeilenumbrüche
$bullets = @()
if ($Notes -match '\|') {
  $bullets = $Notes.Split('|') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
} else {
  $bullets = $Notes.Split("`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
if ($bullets.Count -eq 0) { "Bitte Notes als Text oder Bullet-Liste angeben." | Write-Error }

Set-Content "VERSION" $new -NoNewline

Update-Changelog $new $bullets
Update-Readme $new $bullets

git add VERSION CHANGELOG.md README.md
git commit -m "chore(release): v$new"
git tag "v$new"

git push
git push --tags

Write-Host "✅ Released v$new" -ForegroundColor Green
