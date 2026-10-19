#!/bin/zsh
# Procesa la voz de las grabaciones de la charla: limpieza, EQ de presencia,
# nivelado entre speakers (dynaudnorm), compresion y loudness -16 LUFS.
# El video se copia sin recodificar. Uso: procesar_voz.sh CARPETA_CRUDO CARPETA_SALIDA
IN="${1:?carpeta con los videos crudos}"
OUT="${2:?carpeta de salida (_voz)}"
mkdir -p "$OUT"
CHAIN="highpass=f=90,afftdn=nf=-30:nr=10:tn=1,equalizer=f=280:t=q:w=1.2:g=-3,equalizer=f=1200:t=q:w=1.5:g=1,equalizer=f=3000:t=q:w=1.2:g=3.5,equalizer=f=6500:t=q:w=1.5:g=1.5,dynaudnorm=f=200:g=11:p=0.9:m=12:r=0.25,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,loudnorm=I=-16:TP=-1.5:LRA=6,alimiter=limit=0.89"
for f in "$IN"/*.mp4(N) "$IN"/*.MP4(N) "$IN"/*.mov(N); do
  b=${f:t:r}
  o="$OUT/${b}_voz.mp4"
  ffmpeg -y -loglevel error -i "$f" -map 0:v:0 -map 0:a:0 -c:v copy -af "$CHAIN" -c:a aac -b:a 256k -ar 48000 -movflags +faststart "$o" </dev/null && echo "ok $b" || echo "ERROR $b"
done
echo FIN
