$GITHUB_USER = "leopaiva33"
$GITHUB_TOKEN = $env:GITHUB_TOKEN  # defina: $env:GITHUB_TOKEN = "seu_pat_aqui"
$REPO_NAME   = "universo-aquarismo"
$REPO_URL    = "https://" + $GITHUB_USER + ":" + $GITHUB_TOKEN + "@github.com/" + $GITHUB_USER + "/" + $REPO_NAME + ".git"
$SOURCE_DIR  = $PSScriptRoot
$CLONE_DIR   = "$env:TEMP\ua-publish"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Universo Aquarismo - Publicar Artigo" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERRO: Git nao encontrado." -ForegroundColor Red
    exit 1
}

# Limpar clone anterior
if (Test-Path $CLONE_DIR) {
    Remove-Item -Recurse -Force $CLONE_DIR
}

# Clonar repo existente
Write-Host "Clonando repositorio do GitHub..." -ForegroundColor Green
git clone $REPO_URL $CLONE_DIR 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO ao clonar." -ForegroundColor Red
    exit 1
}

# Copiar tudo do source para o clone (exceto node_modules, .git e package-lock)
Write-Host "Sincronizando arquivos..." -ForegroundColor Green
$excludes = @("node_modules", ".git", "package-lock.json", "dist", ".astro")
robocopy $SOURCE_DIR $CLONE_DIR /E /XD $excludes /XF "package-lock.json" /NJH /NJS /NFL /NDL | Out-Null

# Remover package-lock.json e node_modules do clone se existirem
Remove-Item -Force (Join-Path $CLONE_DIR "package-lock.json") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $CLONE_DIR "node_modules") -ErrorAction SilentlyContinue

# Confirmar que .github foi copiado
$workflowFile = Join-Path $CLONE_DIR ".github\workflows\publicar-artigo.yml"
if (Test-Path $workflowFile) {
    Write-Host "  .github/workflows/publicar-artigo.yml: OK" -ForegroundColor Gray
} else {
    Write-Host "  AVISO: workflow nao encontrado no clone!" -ForegroundColor Yellow
}

# Commit e push
Set-Location $CLONE_DIR
git config user.name $GITHUB_USER
git config user.email "$GITHUB_USER@users.noreply.github.com"

# Remover node_modules do tracking se foi comitado antes
git rm -r --cached node_modules 2>&1 | Out-Null
git rm --cached package-lock.json 2>&1 | Out-Null

git add -A

$changed = git diff --cached --name-only
Write-Host ""
Write-Host "Arquivos para commit:" -ForegroundColor Yellow
if ($changed) {
    Write-Host $changed -ForegroundColor Gray
} else {
    Write-Host "Nenhuma alteracao detectada." -ForegroundColor Yellow
    Set-Location $SOURCE_DIR
    exit 0
}

git commit -m "feat: GitHub Actions + novos artigos e configs"
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "  SUCESSO! Publicado no GitHub!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "  https://github.com/$GITHUB_USER/$REPO_NAME" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "ERRO no push." -ForegroundColor Red
}

Set-Location $SOURCE_DIR
