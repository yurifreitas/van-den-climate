# Sobe a Central de Risco inteira.  Uso:  .\run.ps1
#
# Portas proprias do projeto, nunca as default (8000/5173/8501): as default
# colidem com qualquer outro projeto aberto na maquina, e o sintoma e pior que
# um erro — o front sobe e conversa com a API errada.
$API_PORT   = 8437
$WEB_PORT   = 5931
$DEBUG_PORT = 8601   # Streamlit, ferramenta interna (ADR-015)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Stop-Port($port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

# Sempre limpar antes de subir: uma instancia velha na mesma porta serve codigo
# antigo silenciosamente, que e a forma mais cara de "nao funciona".
Stop-Port $API_PORT
Stop-Port $WEB_PORT

Start-Process -WindowStyle Hidden -WorkingDirectory $root `
    -FilePath 'python' -ArgumentList @('-m','uvicorn','api.main:app','--port',"$API_PORT")

Start-Process -WindowStyle Hidden -WorkingDirectory (Join-Path $root 'web') `
    -FilePath 'npm.cmd' -ArgumentList @('run','dev')

Write-Host ""
Write-Host "  API    http://127.0.0.1:$API_PORT/docs"
Write-Host "  FRONT  http://localhost:$WEB_PORT"
Write-Host "  debug  streamlit run app/main.py --server.port $DEBUG_PORT"
Write-Host ""
Write-Host "  parar:  .\stop.ps1"
