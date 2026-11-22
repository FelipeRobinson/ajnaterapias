# Ajna Terapias - faz tudo para rodar o site localmente.
# Uso, na pasta do projeto:   powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
# Para criar/atualizar o administrador antes de iniciar:   ... -File .\iniciar.ps1 -Admin

param([switch]$Admin)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Ambiente virtual (só na primeira vez)
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Criando ambiente virtual..."
    $py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (-not (Test-Path $py)) { $py = "py" }
    & $py -m venv .venv
}
$python = ".\.venv\Scripts\python.exe"

# 2. Dependências
Write-Host "Instalando dependencias..."
& $python -m pip install -q -r requirements.txt

# 3. Arquivo .env com uma chave secreta gerada (só na primeira vez)
if (-not (Test-Path ".env")) {
    $key = & $python -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content "docs/.env.example") -replace "gere-uma-chave-aleatoria-longa-aqui", $key | Set-Content ".env" -Encoding utf8
    Write-Host "Arquivo .env criado."
}

# 4. Administrador (com -Admin)
if ($Admin) { & $python backend\seed_admin.py }

# 5. Servidor
Write-Host "Abra http://127.0.0.1:5000/login   (Ctrl+C para parar)"
& $python backend\run.py
