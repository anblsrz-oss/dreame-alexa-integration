# Dreame D10 Plus Gen 2 → Alexa (vía Home Assistant en el VPS de alce-fiscal)

Guía paso a paso para controlar el robot por voz con Alexa, sin depender de una
skill oficial de Dreame (que ya no existe para México). Arquitectura:

```
Alexa (voz) → Skill privada → AWS Lambda (gratis) → HTTPS (Nginx + Let's Encrypt)
            → Home Assistant (Docker, en el droplet de alce-fiscal) → integración dreame-vacuum (HACS)
            → cuenta Dreamehome → robot D10 Plus
```

Archivos de este repo:
- `docker-compose.yml` — levanta Home Assistant en el VPS.
- `nginx/homeassistant.conf` — reverse proxy HTTPS.
- `homeassistant/configuration-snippet.yaml` — bloques a fusionar en la config de HA.

**Dominio:** `ha.alexa.alce-soft.com`

**VPS compartido con producción:** este Home Assistant vive en el mismo
droplet que la app fiscal de producción (`alce-droplet`), que ya corre
alce-fiscal + postgres + scraper + n8n + elegance-reels con RAM ajustada
(1.9 GiB, con swap ya parcialmente en uso). Por eso el `docker-compose.yml`
de aquí:
- No usa `privileged`/`network_mode: host` (no hace falta: la integración es
  100% cloud, no hay descubrimiento en la LAN del VPS).
- Publica el puerto 8123 solo en `127.0.0.1` (nginx en el host hace el proxy;
  no queda expuesto directo a internet).
- Trae `mem_limit: 768m` / `memswap_limit: 1024m` para acotar HA y que no
  arrastre a swap pesado al resto de los servicios (incluida la app fiscal
  de clientes reales). **Ojo con bajar este límite:** medido en producción,
  HA pelado usa ~338 MiB, y con HACS + la integración Dreame se pone en
  ~442 MiB en reposo. Con `512m` el kernel lo mataba en bucle
  (*"Memory cgroup out of memory: Killed process python3"*) — ver la nota
  completa en `docker-compose.yml` y en `CONTEXTO.md`.

Antes de levantar el contenedor, conviene revisar RAM disponible en el
droplet (`free -h`) — si "available" está muy bajo, ver `CONTEXTO.md` antes
de continuar.

---

## Paso 1 — Levantar Home Assistant en el VPS

Por SSH al droplet (`ssh alce-droplet`), en `/opt/dreame-ha` (clonando este
repo si lo subes a git, separado de `/opt/alce-fiscal`):

```bash
mkdir -p homeassistant/config
docker compose up -d
```

Verifica que responda localmente (el puerto solo escucha en localhost):

```bash
curl -I http://127.0.0.1:8123
```

Para crear tu usuario admin de Home Assistant la primera vez, sin abrir el
puerto a internet, usa un túnel SSH desde tu máquina:

```bash
ssh -L 8123:127.0.0.1:8123 alce-droplet
```

y entra a `http://localhost:8123` en tu navegador.

## Paso 2 — Dominio + HTTPS válido

1. Crea un registro DNS tipo A: `ha.alexa.alce-soft.com` → IP del droplet
   (`165.227.209.218`). Este paso lo haces tú en tu proveedor de DNS — no
   está automatizado aquí.
2. Nginx y Certbot ya están instalados en el droplet (los usa alce-fiscal).
   Si no lo estuvieran: `sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx`.
3. Copia `nginx/homeassistant.conf` a `/etc/nginx/sites-available/homeassistant`
   y enlázalo (el dominio ya viene resuelto en el archivo):
   ```bash
   sudo ln -s /etc/nginx/sites-available/homeassistant /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
4. Cuando el DNS ya resuelva, emite el certificado (Certbot edita el `.conf`
   automáticamente):
   ```bash
   sudo certbot --nginx -d ha.alexa.alce-soft.com
   ```
5. Confirma que `https://ha.alexa.alce-soft.com` carga Home Assistant con
   candado válido (sin advertencias del navegador).
6. Aplica el snippet `homeassistant/configuration-snippet.yaml` dentro de
   `homeassistant/config/configuration.yaml` (bloque `http:` con
   `trusted_proxies`) y reinicia:
   ```bash
   docker compose restart homeassistant
   ```
   **Si Home Assistant ya había arrancado antes sin este bloque**, el YAML de
   `http:` queda ignorado para siempre (se migra a almacenamiento interno solo
   en el primer arranque — ver la nota completa en
   `homeassistant/configuration-snippet.yaml`). En ese caso, o bien completas
   el onboarding y configuras "Usar X-Forwarded-For" + "Proxies de confianza"
   desde **Configuración → Sistema → Red** en la UI, o editas directamente
   `homeassistant/config/.storage/http` (con el contenedor detenido) para
   añadir `use_x_forwarded_for: true` y `trusted_proxies` dentro de
   `data.stable`. Si ves en los logs `docker logs homeassistant` el error
   *"HTTP integration is not set-up for reverse proxies"* pese a tener el
   YAML correcto, es justo este caso.

## Paso 3 — Vincular el robot (integración Dreame Vacuum vía HACS)

1. Instala **HACS** en Home Assistant siguiendo https://hacs.xyz/docs/use/download/download/
   (requiere reiniciar HA una vez instalado).
2. En Home Assistant: **Configuración → Dispositivos y servicios → HACS →
   Integraciones → Explorar y descargar repositorios**, busca
   `Tasshack/dreame-vacuum` (si no aparece, añádelo como repositorio
   personalizado con la URL `https://github.com/Tasshack/dreame-vacuum`).
3. Reinicia Home Assistant tras instalar.
4. **Configuración → Dispositivos y servicios → Añadir integración → Dreame
   Vacuum**. Cuando pida cuenta, usa el **correo y contraseña de la app
   Dreamehome** (modo cloud — el VPS no está en tu red local, así que no uses
   el modo "local/IP").
5. Debería aparecer una entidad `vacuum.dreame_...` y entidades de habitación
   generadas automáticamente. Pruébalo desde el dashboard de HA (iniciar,
   pausar, limpiar una zona) antes de seguir con Alexa.

## Paso 4 — Configurar el bloque `alexa:` en Home Assistant

Ya está en `homeassistant/configuration-snippet.yaml` — pero **espera al Paso
5** para llenar `client_id`/`client_secret` con los valores reales que generes
en la skill, luego reinicia Home Assistant.

## Paso 5 — Crear la skill privada en Alexa Developer Console

1. Crea/entra a tu cuenta en https://developer.amazon.com/alexa/console/ask
   (gratis, con tu cuenta de Amazon).
2. **Create Skill** → nombre (ej. "Mi Casa") → modelo **Smart Home** → método
   **Provision your own** (no publiques en la tienda, quedará privada/en modo
   desarrollo).
3. En la sección **Account Linking** de la skill, configura:
   - Authorization URI: `https://ha.alexa.alce-soft.com/auth/authorize`
   - Access Token URI: `https://ha.alexa.alce-soft.com/auth/token`
   - Client ID: `https://pitangui.amazon.com/` (o el dominio Alexa de tu
     región — revisa la tabla oficial en la doc de HA si usas otra región)
   - Client Secret: cualquier cadena que inventes (Home Assistant no la valida,
     pero debe coincidir con la que pongas en `configuration.yaml`)
   - Scope: `smart_home`
4. Copia el **Skill ID** (lo necesitas en el paso 6) y pega el mismo
   `client_id`/`client_secret` en `homeassistant/configuration-snippet.yaml`,
   luego reinicia Home Assistant.

## Paso 6 — Función AWS Lambda (puente, gratis)

1. Crea cuenta AWS si no tienes (https://aws.amazon.com/) — no se cobra
   mientras te mantengas en el free tier (ver nota de costos abajo).
2. En **IAM**, crea un rol para Lambda con la política gestionada
   `AWSLambdaBasicExecutionRole`.
3. En **Lambda**, crea una función nueva:
   - Runtime: Python 3.12
   - Región: **us-east-1** (Norteamérica/México) — debe coincidir con la
     región que use tu skill de Alexa.
   - Rol de ejecución: el creado en el paso anterior.
4. Reemplaza el código de ejemplo por el script oficial de Home Assistant:
   https://gist.github.com/matt2005/744b5ef548cc13d88d0569eea65f5e5b
5. Variables de entorno de la función:
   - `BASE_URL` = `https://ha.alexa.alce-soft.com` (sin `/` al final)
   - (`DEBUG=True` opcional mientras pruebas)
6. Añade un **trigger "Alexa Smart Home"** e ingresa el Skill ID del paso 5.
7. Copia el **ARN** de la función Lambda y pégalo en el campo **Default
   endpoint** de la skill, en Alexa Developer Console (pestaña Smart Home).

## Paso 7 — Probar

**Importante — en el mercado de México la skill privada NO aparece en ningún
buscador de la app de Alexa** (ni en el buscador general ni existe la
categoría "Dev" que sí existe en EE.UU./UK). La forma que sí funciona:

1. En la consola de Alexa Developer, completa **primero** el checklist de
   "Skill Preview" (obligatorio incluso para beta test, no solo para
   publicar): categoría, ícono pequeño 108×108 y grande 512×512 (hay unos
   genéricos en `assets/`), descripción corta y detallada, un "Example
   Phrase", Privacy & Compliance (todo "No" + marcar export compliance), y
   una Privacy Policy URL (usa `PRIVACY.md` de este repo vía
   `raw.githubusercontent.com`).
2. Ve a **Distribution → Availability → Beta Test**, agrega tu correo (y el
   de quien más vaya a usarla) como tester, y dale **"Copy link"**.
3. Abre ese link **en el navegador normal del celular (Chrome/Safari), no
   dentro de la app de Alexa** — si lo abres desde dentro de la app, el login
   de Home Assistant puede quedarse en loop (dale Allow y regresa a la misma
   pantalla). Si eso pasa, copia la URL de esa pantalla y ábrela en una
   pestaña nueva de Chrome normal.
4. Acepta los "Skill Beta Testing Terms" e inicia sesión con tu usuario de
   Home Assistant cuando te lo pida (account linking).
5. Ya vinculada, en la app de Alexa di **"Alexa, descubre dispositivos"** —
   debería encontrar el robot y, si ya hiciste el Paso 8, las zonas.
6. Prueba: *"Alexa, enciende [nombre del robot]"* para iniciar limpieza,
   *"Alexa, apaga [nombre del robot]"* para detener/regresar a base.
7. Crea una rutina en la app de Alexa que incluya el dispositivo del robot.

## Paso 8 — Limpieza por zona (opcional)

El modelo de dispositivo "vacuum" de Alexa solo soporta encender/apagar, no
"limpia la zona X" por nombre libre. La forma de lograrlo es con scripts:

1. Encuentra el `room_id` de cada zona: **Herramientas de desarrollador →
   Estados** → abre `camera.<tu_vacuum>_map` → revisa el atributo `rooms`
   (cada una trae `room_id` y `name`, que puedes cruzar contra el mapa visual
   de la entidad para saber cuál habitación es cuál).
2. Fusiona `homeassistant/scripts-zonas.yaml` dentro de tu `scripts.yaml`
   (ajustando `entity_id` y los números de `segments` a tus propios
   `room_id`).
3. Agrega esos scripts al filtro del bloque `alexa:` en
   `homeassistant/configuration-snippet.yaml` (`include_entities`).
4. Reinicia Home Assistant y vuelve a decir "Alexa, descubre dispositivos".
5. Ya puedes decir **"Alexa, limpiar cocina"** (o "Alexa, enciende limpiar
   cocina") y limpia solo esa zona — Home Assistant expone los `script.*`
   como activables por voz de forma nativa, sin necesitar switches
   intermedios.

---

## Notas de costo

- **AWS Lambda**: free tier permanente de 1,000,000 invocaciones/mes — el uso
  doméstico de esta skill nunca se acerca a ese límite. Costo esperado: **$0/mes**.
- **AWS/Amazon Developer**: cuentas gratuitas.
- **Dominio**: si no tienes uno, ~$10-15 USD/año (único costo recurrente real
  de esta configuración, aparte del VPS que ya pagas).

## Notas importantes

- El robot usa comandos tipo "encender/apagar" en el modelo de dispositivo
  Alexa para vacuum. La limpieza por zona ("limpiar cocina") ya está resuelta
  vía scripts — ver Paso 8.
- La integración `Tasshack/dreame-vacuum` tiene dos versiones en HACS: la
  **estable** solo hace login contra la nube de Xiaomi (falla con cuentas
  Dreamehome puras, error "Could not login, check the credentials"), la
  **beta** sí soporta login directo con cuenta Dreamehome. Usa la beta
  (HACS → la integración → ⋮ → Redownload → marcar "show beta versions").
- Si Alexa rechaza el ARN de Lambda con el error *"Please make sure that
  'Alexa Smart Home' is selected for the event source type"* aunque
  `aws lambda get-policy` ya muestre el `EventSourceToken` correcto, revisa
  el `Principal` del permiso: debe ser `alexa-connectedhome.amazon.com`, no
  `alexa-appkit.amazon.com` (ese es para skills custom/de conversación).
- Si cambias la IP del VPS o vence el certificado sin renovarse
  automáticamente (Certbot instala renovación automática vía cron/systemd
  timer, verifícalo con `sudo certbot renew --dry-run`), el control por voz
  dejará de funcionar hasta corregirlo.
