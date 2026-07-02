# Firma los binarios de PureLauncher con el certificado "Pure Studios".
# Crea el certificado de firma de codigo (autofirmado) la primera vez y lo
# guarda en el almacen del usuario (Cert:\CurrentUser\My).
param([Parameter(Mandatory = $true)][string[]]$Files)

$subject = 'CN=Pure Studios, O=Pure Studios'

$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
    Where-Object { $_.Subject -eq $subject } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

if (-not $cert) {
    Write-Host 'Creando certificado de firma "Pure Studios"...'
    $cert = New-SelfSignedCertificate -Type CodeSigningCert `
        -Subject $subject `
        -FriendlyName 'Pure Studios Code Signing' `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyAlgorithm RSA -KeyLength 3072 `
        -NotAfter (Get-Date).AddYears(10)
}

# Con "powershell -File" los argumentos llegan como una sola cadena:
# admitir listas separadas por comas.
$expanded = @()
foreach ($f in $Files) { $expanded += ($f -split ',') }

$ok = $true
foreach ($f in $expanded) {
    try {
        $r = Set-AuthenticodeSignature -FilePath $f -Certificate $cert `
            -HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com' `
            -ErrorAction Stop
        Write-Host ("firmado: {0} [{1}]" -f (Split-Path $f -Leaf), $r.Status)
    } catch {
        Write-Host ("ERROR firmando {0}: {1}" -f $f, $_.Exception.Message)
        $ok = $false
    }
}
if (-not $ok) { exit 1 }
