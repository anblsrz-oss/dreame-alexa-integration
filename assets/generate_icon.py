from PIL import Image, ImageDraw
import sys

def make_icon(size, path):
    img = Image.new("RGBA", (size, size), (37, 99, 235, 255))  # fondo azul
    draw = ImageDraw.Draw(img)

    margin = size * 0.12
    body_box = [margin, margin, size - margin, size - margin]

    # cuerpo circular del robot (gris claro con borde oscuro)
    draw.ellipse(body_box, fill=(230, 230, 235, 255), outline=(40, 40, 45, 255), width=max(2, size // 40))

    # anillo interior (detalle de la carcasa)
    inner_margin = size * 0.22
    inner_box = [inner_margin, inner_margin, size - inner_margin, size - inner_margin]
    draw.ellipse(inner_box, outline=(160, 160, 170, 255), width=max(1, size // 60))

    # sensor/camara central (circulo oscuro)
    sensor_r = size * 0.09
    cx, cy = size / 2, size / 2
    draw.ellipse([cx - sensor_r, cy - sensor_r, cx + sensor_r, cy + sensor_r], fill=(30, 30, 35, 255))
    # brillo del sensor
    hl_r = sensor_r * 0.35
    draw.ellipse([cx - hl_r * 2, cy - hl_r * 2.2, cx - hl_r * 0.5, cy - hl_r * 0.7], fill=(90, 160, 255, 255))

    # luz de estado (punto verde arriba)
    light_r = size * 0.045
    lx, ly = size * 0.5, size * 0.28
    draw.ellipse([lx - light_r, ly - light_r, lx + light_r, ly + light_r], fill=(60, 200, 100, 255))

    # dos "ruedas/cepillos" laterales sutiles abajo
    wheel_r = size * 0.05
    wy = size * 0.82
    draw.ellipse([size * 0.28 - wheel_r, wy - wheel_r, size * 0.28 + wheel_r, wy + wheel_r], fill=(40, 40, 45, 255))
    draw.ellipse([size * 0.72 - wheel_r, wy - wheel_r, size * 0.72 + wheel_r, wy + wheel_r], fill=(40, 40, 45, 255))

    img.save(path)

make_icon(512, "assets/icon_large_512.png")
make_icon(108, "assets/icon_small_108.png")
print("OK")
