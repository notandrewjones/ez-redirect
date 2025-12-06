# Requires admin privileges

Write-Host "Installing ez-redirect..."

# Install Python if missing
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is required. Please install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
}

# Install NSSM (Windows service manager)
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    Write-Host "Downloading NSSM..."
    Invoke-WebRequest "https://nssm.cc/release/nssm-2.24.zip" -OutFile "nssm.zip"
    Expand-Archive "nssm.zip" -DestinationPath "C:\nssm-temp" -Force
    Move-Item "C:\nssm-temp\nssm-2.24\win64\nssm.exe" "C:\nssm\nssm.exe" -Force
    Remove-Item "C:\nssm-temp" -Recurse -Force
    Remove-Item "nssm.zip"
}

# Install directory
$installDir = "C:\ez-redirect"

if (-not (Test-Path $installDir)) {
    git clone https://github.com/YOUR_GITHUB_USERNAME/ez-redirect.git $installDir
} else {
    cd $installDir
    git pull
}

# Install Python deps
pip install fastapi uvicorn[standard]

# Create Windows Service
$nssm = "C:\nssm\nssm.exe"
& $nssm install ez-redirect "python" "uvicorn backend.app:app --host 0.0.0.0 --port 8000"

Write-Host "Starting ez-redirect service..."
& $nssm start ez-redirect

Write-Host "Installation complete."
Write-Host "Open your browser to http://localhost:8000"
