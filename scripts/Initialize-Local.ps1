$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"

if (Test-Path -LiteralPath $envPath) {
    Write-Output "An existing .env was found and has not been changed."
    exit 0
}

$bytes = New-Object byte[] 48
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $generator.GetBytes($bytes)
} finally {
    $generator.Dispose()
}
$secret = [Convert]::ToBase64String($bytes)
$content = "SECRET_KEY=$secret`nFRONTEND_ORIGIN=http://localhost:5173`n"
$stream = [System.IO.File]::Open($envPath, [System.IO.FileMode]::CreateNew)
try {
    $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
    try {
        $writer.Write($content)
    } finally {
        $writer.Dispose()
    }
} finally {
    $stream.Dispose()
}
Write-Output "Created the git-ignored .env with a random signing key. Do not share or commit it."
