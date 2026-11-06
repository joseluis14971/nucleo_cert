#!/bin/bash
# Agrega CertiNexo al pie de nucleocert.com (idempotente, con copia previa)
set -euo pipefail
F=${1:-/var/www/nucleocert/index.html}
[ -f "$F" ] || { echo "No existe $F"; exit 1; }
if grep -q "certinexo.com" "$F"; then echo "Ya tiene CertiNexo, no hago nada."; exit 0; fi
mkdir -p /root/backups_manual
cp "$F" "/root/backups_manual/nucleocert_index_$(date +%Y%m%d_%H%M).html"
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding='utf-8').read()
ancla = 'nucleolaboratorios.com</a></p>\n</footer>'
assert s.count(ancla) == 1, 'no encuentro el pie de página'
nuevo = ('nucleolaboratorios.com</a></p>\n  <p style="font-size:.7rem;color:rgba(255,255,255,.4);margin-top:6px;">Más de Núcleo: '
         '<a href="https://certinexo.com" target="_blank" rel="noopener" style="color:rgba(255,255,255,.4)">CertiNexo</a>, la red social cripto de la comunidad</p>\n</footer>')
open(p, 'w', encoding='utf-8').write(s.replace(ancla, nuevo)); print('OK: CertiNexo agregado al pie de nucleocert.com')
PY
