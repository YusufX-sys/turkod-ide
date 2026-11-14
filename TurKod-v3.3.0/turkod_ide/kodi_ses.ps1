# Kodi'nin sesi: metni Windows'un Türkçe sesiyle (OneCore, ör. Tolga) WAV'a çevirir.
# Kullanım: powershell -NoProfile -File kodi_ses.ps1 <metin.txt> <cikti.wav>
param([string]$Girdi, [string]$Cikti)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Bekle($islem, $tur) {
    $g = $asTask.MakeGenericMethod($tur).Invoke($null, @($islem))
    $g.Wait(-1) | Out-Null
    $g.Result
}
$metin = [IO.File]::ReadAllText($Girdi, [Text.Encoding]::UTF8)
$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$ses = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object { $_.Language -eq 'tr-TR' } | Select-Object -First 1
if ($ses) { $s.Voice = $ses } else { Write-Output 'TURKCE_SES_YOK' }
try { $s.Options.SpeakingRate = 1.05; $s.Options.AudioPitch = 1.25 } catch {}
$akis = Bekle ($s.SynthesizeTextToStreamAsync($metin)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$okuyucu = New-Object Windows.Storage.Streams.DataReader($akis.GetInputStreamAt(0))
$null = Bekle ($okuyucu.LoadAsync([uint32]$akis.Size)) ([uint32])
$bayt = New-Object byte[] $akis.Size
$okuyucu.ReadBytes($bayt)
[IO.File]::WriteAllBytes($Cikti, $bayt)
