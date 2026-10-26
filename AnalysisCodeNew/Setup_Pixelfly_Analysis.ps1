$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirements = Join-Path $repositoryRoot "requirements-pixelfly.txt"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m pip install -r $requirements
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m pip install -r $requirements
}
else {
    throw "Python 3 was not found. Install Python 3 or Anaconda first."
}

if ($LASTEXITCODE -ne 0) {
    throw "Python package installation failed with exit code $LASTEXITCODE."
}

Write-Host "Pixelfly analysis dependencies are installed."
