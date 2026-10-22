import hashlib
import json
import sys
import zipfile
from pathlib import Path

from loguru import logger
logger.remove()
from androguard.core.apk import APK
from androguard.core.dex import DEX

path = Path(sys.argv[1])
apk = APK(str(path))
print(json.dumps({
    "package": apk.get_package(), "version": apk.get_androidversion_name(),
    "sha256": hashlib.file_digest(path.open('rb'), 'sha256').hexdigest(),
    "signer_certificate_sha256": [hashlib.sha256(c).hexdigest()
                                  for c in apk.get_certificates_der_v2()],
}, indent=2))
with zipfile.ZipFile(path) as archive:
    for name in archive.namelist():
        if not name.endswith('.dex'):
            continue
        dex = DEX(archive.read(name))
        for cls in dex.get_classes():
            cn = cls.get_name()
            if not cn.startswith('Lcom/tibber/'):
                continue
            for method in cls.get_methods():
                mn = method.get_name()
                if not (('SmartChargingViewModel' in cn and
                         any(k in mn for k in ['Departure', 'performVehicleAction']))
                        or ('Gateway' in cn and 'Vehicle' in cn and
                            any(k in mn.lower() for k in ['action', 'setting']))):
                    continue
                print('\nMETHOD', cn, mn, method.get_descriptor())
                for ins in method.get_instructions():
                    print(ins.get_name(), ins.get_output())
