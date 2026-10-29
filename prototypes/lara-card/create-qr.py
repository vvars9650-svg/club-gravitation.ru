"""Generate and independently decode the QR for the current TEST card."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
import qrcode
import qrcode.image.svg
import zxingcpp
from PIL import Image

URL = 'https://test.club-gravitation.ru/card/lara/'
out = ROOT / 'exports'
out.mkdir(exist_ok=True)
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=20, border=4)
qr.add_data(URL)
qr.make(fit=True)
png = out / 'lara-card-qr-TEST.png'
svg = out / 'lara-card-qr-TEST.svg'
qr.make_image(fill_color='black', back_color='white').save(png)
qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage).save(svg)
original = Image.open(png).convert('RGB')
checks = []
for size in [original.width, 240, 180]:
    image = original if size == original.width else original.resize((size, size), Image.Resampling.NEAREST)
    decoded = zxingcpp.read_barcode(image)
    assert decoded and decoded.text == URL, f'QR decode failed at {size}px'
    checks.append({'size': size, 'decoded': decoded.text})
report = {'url': URL, 'environment': 'TEST', 'errorCorrection': 'Q', 'quietZoneModules': 4,
          'pngSize': list(original.size), 'checks': checks}
(out / 'lara-card-qr-TEST-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
