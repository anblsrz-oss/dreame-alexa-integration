# Contexto del proyecto: Dreame D10 Plus Gen 2 → Alexa

**Objetivo:** controlar por voz con Alexa un robot aspiradora **Dreame D10 Plus
Gen 2** (iniciar limpieza, limpiar zonas específicas, usarlo en rutinas de
Alexa). La skill oficial de Dreame para Alexa ya no existe/no está disponible
en México, y publicar una skill propia que la reemplace no es viable (las
skills smart-home de Alexa deben hablar con la nube privada real del
fabricante).

**Por qué esta ruta:** se intentó vincular el robot con la app Xiaomi Home /
Mi Home primero — falló, porque el D10 Plus Gen 2 usa la nube/app propia de
Dreame (**Dreamehome**), separada de Xiaomi, no Mi Home.

## Arquitectura elegida (confirmada con investigación web, sept. 2026)

```
Alexa (voz) → skill privada de Alexa Smart Home → AWS Lambda (puente, Python, free tier permanente)
            → HTTPS (dominio propio + Let's Encrypt) → Nginx reverse proxy en el VPS del usuario
            → Home Assistant (Docker, en el VPS) → integración dreame-vacuum (HACS)
            → cuenta Dreamehome → robot Dreame D10 Plus
```

- La integración comunitaria de Home Assistant `Tasshack/dreame-vacuum` (vía
  HACS) soporta explícitamente `dreame.vacuum.r2205` (D10 Plus) — en modo
  cloud usando las credenciales de Dreamehome (no modo local, porque Home
  Assistant corre en un VPS remoto, no en la misma red que el robot).
- El componente nativo `alexa.smart_home` de Home Assistant permite crear una
  skill de Alexa **privada** (nunca publicada) usando los endpoints OAuth
  propios de Home Assistant (`/auth/authorize`, `/auth/token`).
- El puente requiere una función **AWS Lambda** (código oficial de Home
  Assistant en https://gist.github.com/matt2005/744b5ef548cc13d88d0569eea65f5e5b)
  — gratis indefinidamente a este nivel de uso (free tier permanente de
  Lambda: 1,000,000 invocaciones/mes).
- El usuario ya tiene un **VPS en DigitalOcean** — no se necesita hardware
  nuevo (ej. Raspberry Pi). **Decisión (sept. 2026):** se instala en el mismo
  droplet que ya usa el proyecto `alce-fiscal` (`alce-droplet`,
  165.227.209.218, 1.9 GiB RAM), no en un droplet separado. Ese droplet
  aloja producción real (alce-fiscal + postgres con datos fiscales de
  clientes + scraper + n8n + elegance-reels) y ya está justo de RAM (al
  revisar: solo ~750 MiB "available", swap ya al ~50% de uso). Mitigación
  elegida: `mem_limit: 768m` / `memswap_limit: 1024m` en el contenedor de
  Home Assistant y sin `privileged`/`network_mode: host` (innecesario porque
  la integración es cloud, no LAN) — puerto 8123 solo en `127.0.0.1`, nginx
  del host hace el proxy HTTPS. Detalle completo en `README.md`.
- **Dominio elegido:** `ha.alexa.alce-soft.com` (subdominio bajo el dominio
  que ya usa alce-fiscal). El registro DNS tipo A lo crea el usuario — no hay
  automatización de DNS disponible en este entorno.
- **Ruta en el droplet:** `/opt/dreame-ha` (separado de `/opt/alce-fiscal`).
- Alternativa descartada: Nabu Casa / Home Assistant Cloud (~$6.5 USD/mes) —
  más simple (sin configurar Lambda/OAuth) pero el usuario prefirió la ruta
  gratuita al self-hosted, ya que tiene el VPS.
- **Pendiente conocido:** el modelo de dispositivo "vacuum" de Alexa solo
  soporta encender/apagar, no "limpia la zona X" por nombre libre. Plan:
  exponer cada zona como un `switch` helper en Home Assistant, cada uno
  disparando un script que llame al servicio de limpieza por zona de la
  integración Dreame, y luego incluir esos switches en el filtro del bloque
  `alexa:`. **Aún no implementado — sigue pendiente.**

## Archivos del proyecto (en esta misma carpeta)

- `docker-compose.yml` — contenedor de Home Assistant, sin `privileged`/
  `network_mode: host`, puerto 8123 solo en `127.0.0.1`, con `mem_limit`.
- `nginx/homeassistant.conf` — reverse proxy HTTPS, ya con el dominio real
  `ha.alexa.alce-soft.com`.
- `homeassistant/configuration-snippet.yaml` — bloques `http:` y
  `alexa: smart_home:`, con placeholders de `client_id`/`client_secret` de la
  skill pendientes de rellenar (paso 5 del README).
- `README.md` — guía completa de 7 pasos: Home Assistant en el VPS → dominio
  + HTTPS → integración HACS + Dreame → configuración `alexa:` → skill privada
  en Alexa Developer Console → función AWS Lambda puente → pruebas.

## Estado actual (27 sept 2026)

**Pasos 1 y 2 del README completados:**
- Home Assistant corriendo en `alce-droplet` (`/opt/dreame-ha`), inicialmente
  con `mem_limit: 512m` (subido después a `768m`, ver más abajo). Verificado
  estable junto al resto de servicios del droplet (alce-fiscal, scraper,
  elegance-reels, n8n).
- DNS `ha.alexa.alce-soft.com` → `165.227.209.218` creado y propagado por el
  usuario (Hostgator cPanel → Zone Editor).
- Certificado Let's Encrypt emitido y desplegado (`certbot --nginx`), sitio
  habilitado en `/etc/nginx/sites-enabled/homeassistant`. `https://ha.alexa.alce-soft.com`
  responde con candado válido.
- **Bug encontrado y resuelto:** el bloque `http:` de YAML se ignoraba
  silenciosamente porque Home Assistant ya había arrancado una vez sin él
  (migración YAML→almacenamiento interno ocurre una sola vez). Se corrigió
  editando directamente `homeassistant/config/.storage/http` (clave
  `data.stable`) con el contenedor detenido — detalle completo en
  `README.md` Paso 2.6 y en `homeassistant/configuration-snippet.yaml`.
  También se corrigió `trusted_proxies` para incluir la subred del bridge de
  Docker (`172.20.0.0/16`), no solo `127.0.0.1`, porque así es como nginx
  (en el host) le llega a Home Assistant a través del puerto publicado.

**Onboarding completado:** usuario admin de Home Assistant creado
(`ha-anbl-srz`) por túnel SSH.

**Paso 3 completado:**
- HACS instalado y `Tasshack/dreame-vacuum` añadido desde HACS (versión beta,
  necesaria para login con cuenta Dreamehome — la versión estable solo
  soporta login contra la nube de Xiaomi y daba "Could not login, check the
  credentials" con una cuenta Dreamehome pura).
- Robot vinculado: *config entry* `Dreame Vacuum` con título `D10 Plus Gen 2`
  y `unique_id` = MAC `70:c9:32:c7:f5:1b`; entidad `vacuum.d10_plus_gen_2`
  registrada y reportando estado `docked` → conexión viva con la nube de
  Dreamehome (modo cloud, como estaba previsto).

**Bug encontrado y resuelto: OOM en bucle (mem_limit 512m insuficiente).**
Con HACS + `dreame_vacuum` el contenedor moría cada ~30 s durante el
arranque. Evidencia: 12 entradas `Memory cgroup out of memory: Killed process
... (python3) ... anon-rss:517340kB` en `dmesg`, con
`oom_memcg=/system.slice/docker-<id>.scope` (el cgroup del propio
contenedor). `docker inspect ... .State.OOMKilled` devolvía `false` y eso
despista: Docker resetea ese campo en cada reinicio, así que **no sirve para
descartar OOM en un contenedor que ya se reinició** — la prueba buena es
`dmesg` o `memory.events` del cgroup.
Consumo medido: HA pelado ~338 MiB, en reposo con HACS + Dreame ~442 MiB,
pico >517 MiB. Se subió a `mem_limit: 768m` / `memswap_limit: 1024m`
(dejando 256 MiB de swap propio a propósito: con `memswap_limit == mem_limit`
cualquier pico transitorio es muerte instantánea). Verificado estable en
441.7 MiB / 768 MiB (57.5%), sin nuevos OOM, HTTP 200 en local y por HTTPS.
También se desactivó el `recorder` (historial/logbook/estadísticas) por
completo — no aporta nada para control por voz y es de lo que más RAM/disco
consume con el tiempo.
**Si algún día se acerca al techo de forma sostenida**, el siguiente recorte
es reemplazar `default_config:` por una lista explícita sin
`radio_browser`/`go2rtc`/`stream` ni los discovery (`ssdp`, `zeroconf`,
`dhcp`, `usb`, `bluetooth`) — en este VPS no hay LAN que descubrir. Si eso
tampoco alcanza, la alternativa de fondo es mover Home Assistant a su propio
droplet (evaluado y descartado por ahora, riesgo aceptado — ver decisión
más abajo).

**Pasos 4, 5 y 6 completados (27 sept 2026):**
- Bloque `alexa:` con los valores reales de la skill aplicado en el
  `configuration.yaml` del droplet (`client_id: https://pitangui.amazon.com/`
  — región Norteamérica, que es la que sirve a México). **El `client_secret`
  NO está en este repo a propósito** (repo público); vive solo en el droplet.
- Skill privada creada en Alexa Developer Console. Skill ID:
  `amzn1.ask.skill.20c9a886-3f35-4f7d-bb4d-b4bedd909fe0`.
- Función AWS Lambda puente desplegada en la cuenta personal de AWS
  (`283449825232`, usuario IAM `dreame-lambda-setup` con permisos acotados a
  Lambda + el rol del puente). Rol: `dreame-alexa-lambda-role`. Función:
  `dreame-alexa-bridge`, Python 3.12, `us-east-1`, código del gist oficial
  (copia local en `lambda/lambda_function.py`), `BASE_URL` como variable de
  entorno.
  ARN: `arn:aws:lambda:us-east-1:283449825232:function:dreame-alexa-bridge`
- Verificado con invocación de prueba: el handler corre, valida
  `payloadVersion` y responde `INVALID_REQUEST` ante un evento sin token
  (comportamiento correcto).

**Bug encontrado y resuelto: permiso de Lambda con el Principal equivocado.**
Al pegar el ARN en la consola de Alexa (Smart Home → Default endpoint) daba
`Failed to save skill information / Please make sure that "Alexa Smart Home"
is selected for the event source type, for provided arn [Invalid value]`,
aunque `aws lambda get-policy` ya mostraba un statement con
`EventSourceToken` = Skill ID correcto. La causa real: el `Principal` del
permiso era `alexa-appkit.amazon.com`, que es el principal para skills
**custom** (conversación), no para **Smart Home**. El correcto es
`alexa-connectedhome.amazon.com`. Se corrigió con:
```
aws lambda remove-permission --function-name dreame-alexa-bridge --statement-id alexa-smart-home --region us-east-1
aws lambda add-permission --function-name dreame-alexa-bridge --statement-id alexa-smart-home \
  --action lambda:InvokeFunction --principal alexa-connectedhome.amazon.com \
  --event-source-token <SKILL_ID> --region us-east-1
```
Tras esto, el ARN se guardó sin problema en la consola de Alexa.

**Riesgo de fondo reconocido y aceptado (27 sept 2026):** aun con estos
ajustes, el droplet compartido sigue muy justo de RAM en general (todo el
sistema, no solo el contenedor de HA). Se decidió **aceptar el riesgo por
ahora** y seguir avanzando en el droplet compartido en vez de migrar a uno
separado, dado que ya quedó estable. Si vuelve a fallar, la opción de
respaldo es un droplet nuevo y dedicado solo para Home Assistant (~$6-12
USD/mes según RAM, 1-2 GB).

## Paso 7 completado — control por voz funcionando de extremo a extremo (27 sept 2026)

**Problema encontrado: la skill de Smart Home en modo dev/beta no aparece en
ningún buscador de la app de Alexa para la cuenta/región de México.**
Se investigó a fondo antes de encontrar la causa: las skills Smart Home
privadas/no publicadas **no son buscables** por diseño (ni en el buscador
general ni en una categoría "Smart Home" de la tienda), y la categoría
**"Dev"** de la tienda de skills (donde normalmente vive esto) **no existe en
absoluto en la tienda de Alexa para México** — se confirmó deslizando toda la
fila de categorías en la app hasta el final sin encontrarla. Se descartaron
en el camino: la API de auto-habilitación de SMAPI (`PUT
/v1/skills/{id}/stages/development/enablement` — responde 403 "You can only
enable custom or music skills", Smart Home queda excluido a propósito) y el
link directo `alexa-skills.amazon.com/apis/custom/skills/{id}/launch`
(también solo válido para skills custom).

**Solución que sí funcionó: Beta Testing.** Desde Distribution → Availability
→ Beta Test, se agregaron como testers los correos del usuario y de quien
administra el droplet, y se generó un "Copy link" de invitación — ese link,
abierto en el navegador del celular, sí permite habilitar una skill Smart
Home sin pasar por ninguna búsqueda ni categoría.

**Requisito previo no obvio:** el Beta Test (igual que la certificación
pública) exige completar todo el checklist de "Skill Preview" aunque nunca se
vaya a publicar: Privacy & Compliance (4 preguntas Sí/No + export compliance),
categoría (Smart Home), ícono pequeño 108×108 y grande 512×512, descripción
corta y detallada, al menos un "Example Phrase", Privacy Policy URL, y
Testing Instructions con usuario/contraseña reales de Home Assistant (campo
no visible a clientes, solo para revisión). Se resolvió:
- `PRIVACY.md` en el repo, servido públicamente vía
  `https://raw.githubusercontent.com/anblsrz-oss/dreame-alexa-integration/master/PRIVACY.md`.
- Íconos generados con Python/Pillow (dibujo simple de un robot aspiradora
  visto desde arriba: cuerpo circular, sensor central, luz de estado, ruedas)
  en `assets/icon_small_108.png` y `assets/icon_large_512.png` (script:
  `assets/generate_icon.py`).
- Descripción detallada reescrita para cumplir las reglas de Amazon: mencionar
  prerrequisitos (instancia propia de Home Assistant con la integración
  Dreame Vacuum configurada), usar la palabra "skill" sin traducir, aclarar
  que no hay afiliación con Amazon ni con Dreame.

**Bug encontrado y resuelto: el account linking se quedaba en loop.**
Al activar la skill desde dentro de la app de Alexa, el login de Home
Assistant se abría en el **navegador integrado de la app de Alexa**
(in-app browser), y tras darle "Allow" regresaba a la misma pantalla en vez
de completar el flujo. La solución fue copiar la URL de esa pantalla y
abrirla en Chrome normal (fuera de la app) — ahí sí completó el login y el
account linking sin problema. **Causa probable:** restricciones de cookies/
sesión del navegador integrado de la app de Alexa con el flujo OAuth de Home
Assistant.

**Resultado final:** cuenta vinculada, "Alexa, descubre dispositivos"
encontró el robot, y se confirmó control por voz real (encender/apagar el
D10 Plus) desde Alexa.

**Pendiente:** las zonas de limpieza como `switch` helpers en Home Assistant
(ver sección de arquitectura arriba) — hoy solo se puede encender/apagar el
robot en general por voz, no limpiar una habitación específica por nombre.
