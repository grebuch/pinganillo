# Escuchator 0.5 · conexión a IA independiente

Conserva los ajustes de calidad de 0.4: small/medium/base, idioma y bloques
que buscan pausas entre 4 y 12 segundos. No pretende funcionar como subtítulos.

## Prueba recomendada

1. Inicia escucha local y confirma que aparece texto.
2. Sin parar el audio, pulsa Continue with ChatGPT y completa la conexión.
3. Elige un modelo devuelto por tu cuenta.
4. Pulsa «Probar IA sin audio». Usa una pregunta de ejemplo, no la reunión.
5. Si funciona, pulsa «Activar IA sin parar transcripción». Se analizarán los
   próximos fragmentos. «Pausar IA» mantiene el registro/transcripción local.

La selección del modo inicial no cambia una sesión ya iniciada. Usa los nuevos
botones para activar o pausar IA durante la escucha. No se reenvían automáticamente
los fragmentos descartados mientras la IA estaba pausada. La transcripción completa
sigue disponible para exportación.

## Límites de espera y diagnóstico

Las peticiones al plan usan límites de conexión/lectura HTTP y un límite de espera
completa de 45 segundos. Si no terminan, se pausa únicamente el análisis y se
muestra el error. El estado IA incluye contador de espera durante el análisis.
No se muestran respuestas parciales como si estuvieran completas.
El límite permite dejar de esperar, pero no cancela de forma garantizada una
petición ya recibida por el servidor. No se inicia otra petición del mismo analizador
mientras su trabajador anterior siga activo. Una reconexión posterior constituye
una nueva sesión/analizador y puede generar otra petición.

Se limita Whisper a hasta cuatro hilos CPU (según núcleos disponibles) para dejar
margen a la interfaz y a la red. No garantiza que el hardware siga el ritmo.

«Guardar diagnóstico» añade estado IA, clase de error, código HTTP si existe y
contadores de colas, sin audio, texto de la reunión ni credenciales. Comparte ese
JSON y la línea de error mostrada, ocultando datos personales, si vuelve a fallar.
Si falla la prueba sin audio, no tiene sentido cambiar la captura: hay que revisar
la autorización/modelo/red y los límites de la cuenta. No se activa API de pago.

Catorce pruebas automatizadas, incluida continuidad de transcripción durante una
espera simulada de IA, timeout, exclusión de peticiones simultáneas y arranque con
widgets simulados. No se ha probado OAuth real ni Windows en este entorno; no se
ha confirmado la causa exacta del bloqueo observado en el PC del usuario.

Las instrucciones anteriores de parar toda la sesión para conectar/probar IA
quedan sustituidas por los pasos de esta versión. Para desconectar la cuenta,
termina la sesión de audio; se conservan las instrucciones anteriores de revocación.

# Escuchator 0.4 · prioridad a calidad de transcripción

Configuración inicial: Whisper small, CPU int8, idioma castellano. Puedes elegir
catalán, inglés o automático. Selecciona el idioma que realmente se habla; si se
alternan varios, usa Automático. Modelo medium como opción más pesada y base
para equipos lentos. Cambiar de modelo descarga sus pesos la primera vez.

Esta versión sustituye los bloques fijos de 3 segundos por bloques que buscan
una pausa desde los 4 segundos y tienen un máximo de 12. La detección de pausas
es una heurística de volumen, no una segmentación lingüística: todavía puede
cortar palabras o frases. Whisper utiliza filtro de voz y búsqueda beam_size=5.
No realimenta la transcripción anterior como prompt, para evitar propagar errores.

El modelo local no depende de tu suscripción ChatGPT. No se añade coste API.
Más precisión puede requerir más CPU y añadir latencia. Prueba small con audio
claro; si tu equipo sigue el ritmo, compara medium. No se garantiza calidad ni
baja latencia hasta probar el mismo audio en tu equipo. No se ha evaluado aquí
la tasa de errores con voz real; once pruebas automatizadas verifican estructura,
parámetros, arranque simulado y flujo, no precisión del reconocimiento.

Las referencias posteriores a modelos base, bloques de 3 segundos o filtro VAD
desactivado describen versiones anteriores y quedan sustituidas por esta nota.

# Corrección de arranque 0.3.1

Se corrige la selección de un índice inexistente durante la creación del selector
de modos. Se añade una prueba de construcción de ventana con widgets simulados.
Pasan once pruebas automatizadas; captura real y GUI nativa pendientes de validar
en Windows. No requiere cambiar cuenta ni activar API de pago.

# Escuchator 0.3.1 · revisión de captura y diagnóstico

Prueba de concepto para Windows 10/11. Captura sonido de una salida de audio,
transcribe localmente y opcionalmente analiza el texto con tu plan ChatGPT.
No se ha validado todavía en el PC del usuario ni con su cuenta. Las pruebas
automatizadas usan dispositivos y modelos simulados: no equivalen a una prueba
real de Teams, reconocimiento de voz ni OAuth.

## Primera prueba, sin cuenta ni pagos

1. Instala Python 3.11 o 3.12 (64 bits), y descomprime en una carpeta nueva.
2. Ejecuta INICIAR.bat y espera a que instale las dependencias.
3. El modo inicial es «Solo transcripción local (diagnóstico)».
4. Mantén «WASAPI nativo (recomendado)» y elige la fuente «Audio del PC» que
   coincida con la salida en la que escuchas Teams o YouTube.
5. Reproduce voz y pulsa Escucha. El medidor debe moverse.
6. Espera a que Whisper esté listo. La primera vez descarga el modelo `base`
   desde Hugging Face, lo que requiere Internet y puede tardar minutos.
7. Debe aparecer texto en «Transcripción en directo». En modo diagnóstico los
   paneles de conceptos y respuestas permanecen vacíos deliberadamente.

El audio no sale del PC en este modo. El programa no necesita ChatGPT para
capturar y transcribir. No activa API de pago por sí solo.

## Si no aparece texto

Cierra Escuchator y ejecuta DIAGNOSTICO.bat, con un vídeo de voz reproduciéndose.
Selecciona el número de la salida que estás escuchando. El script comprueba
8 segundos de captura, nivel de señal, carga del modelo y transcripción.
Genera `diagnostico-escuchator.txt` en esta carpeta, con versiones de paquetes,
nombres de dispositivos y errores. No incluye grabación ni texto reconocido.
Puedes compartir ese informe después de revisar los nombres de dispositivos.
La prueba tiene tiempos máximos de captura; descargar el modelo puede tardar.

También hay un botón «Guardar diagnóstico» en la interfaz. Exporta versiones,
fuente elegida y contadores, sin audio, transcripciones ni tokens. No incluye
el detalle de errores por privacidad: si aparece un error, copia únicamente
la línea del error de la interfaz, ocultando cualquier dato sensible.

Si WASAPI nativo no reconoce la salida, selecciona el motor alternativo
SoundCard y actualiza dispositivos antes de volver a iniciar. Cada motor
mantiene su propia lista. No cambies de dispositivo durante la captura.

## Activar conceptos y respuestas sin una API de pago

Después de confirmar que transcribe:
1. Pausa y espera al procesamiento pendiente.
2. Selecciona «Plan ChatGPT + transcripción local».
3. Pulsa Continue with ChatGPT, completa el flujo en tu navegador y concede
   el permiso de uso del plan. Elige un modelo devuelto por tu cuenta.
4. Pulsa «Probar IA sin audio». Envía SOLO una pregunta de ejemplo sobre RTO.
5. Si la prueba funciona, pulsa Escucha para analizar el audio transcrito.

La integración usa el flujo oficial Sign in with ChatGPT y consume los límites
del plan, sujeto a disponibilidad de cuenta/workspace. No reutiliza cookies ni
sesiones de otras apps. Tener una suscripción no permite asumir que el flujo
funcionará con todas las cuentas: debe probarse. La conexión no concede acceso
a tus conversaciones, recuerdos ni documentos de ChatGPT.

Si falla esta prueba, comparte el error. Cambiar la IA a API puede ser una vía
posterior, pero NO arregla una captura de audio que no entrega muestras.

## Cambios respecto a 0.2.2

- Motor de captura adicional PyAudioWPatch/WASAPI, con frecuencia nativa de la
  salida, conversión a 48 kHz y límite de espera de muestras de 10 segundos.
- SoundCard sigue como alternativa explícita.
- Transcripción local como modo inicial, sin bloqueo por login de ChatGPT.
- Bloques de captura de unos 3 segundos, en lugar de 6.
- Separación de estados de captura, transcripción e IA.
- Entre análisis se esperan al menos 3 segundos después de la respuesta previa,
  agrupando el texto que llegue. Se elimina la espera deliberada de 20 segundos.
- Evita que canales con fase opuesta anulen la voz al convertir a mono.
- Menor umbral de silencio y filtro VAD desactivado para reducir descartes.
  Esto puede aumentar errores de reconocimiento con ruido o música.
- Diagnóstico independiente de la interfaz y prueba independiente de la IA.

## Latencia y límites

No es streaming palabra a palabra. A los bloques de 3 segundos se añaden el
procesamiento local, agrupación y latencia de IA. No se puede garantizar que
la CPU y la red sigan el ritmo. Si el búfer se llena, se avisa de pérdida de
bloques. Pausar puede tardar mientras se completa el trabajo pendiente.

Solo captura una fuente: audio del PC O micrófono. Si seleccionas altavoces,
no se incluyen automáticamente tus intervenciones de micrófono. La salida
predeterminada de Windows puede ser distinta de la de Teams, especialmente
con auriculares Bluetooth. Elige la salida exacta y evita cambiarla durante
la sesión. El texto reconocido puede tener errores; no debe tratarse como
transcripción certificada ni las sugerencias como hechos verificados.

No incluye búsqueda web. El análisis recibe contexto reciente, un resumen
acumulativo y, si lo cargas, documentación .txt/.md UTF-8 hasta 40.000 caracteres.
Puedes exportar la sesión manualmente. No se guarda audio automáticamente.
Los conceptos y respuestas se pueden abrir en ventanas independientes.

## Conexiones y credenciales

Modo Plan: Whisper local; se envía texto a OpenAI para el análisis, con
`store=false` y `stream=true`. Eso no implica ausencia de retención del proveedor.
Tokens OAuth solo en memoria, con renovación durante la sesión. Se guarda un
registro de cuenta/client ID y host ID, sin tokens ni contraseña, en
`%LOCALAPPDATA%\Escucha\registro.json`. «Desconectar» intenta revocar la sesión.
Cerrar borra tokens locales pero no garantiza revocación remota.

Modo «API de pago (opcional)»: requiere selección explícita, clave y confirmación
al iniciar. Envía audio y texto a OpenAI y genera costes de API separados.
No hay cambio automático al modo de pago cuando falla el plan.

## Pruebas

`python -m unittest discover -s tests -v`

Diez pruebas automatizadas: formatos de audio, remuestreo nativo de 44.1 a
48 kHz y 16 kHz para Whisper, canales en contrafase, captura/transcripción sin
cuenta, aislamiento de errores IA, contexto y deduplicación, callback OAuth,
parámetros de streaming y rechazo de respuestas incompletas. Hardware Windows,
modelo Whisper real y autorización de cuenta pendientes de validar.

Código bajo licencia MIT. No se ha publicado externamente.

Referencias:
- https://github.com/s0d3s/PyAudioWPatch
- https://github.com/bastibe/SoundCard
- https://github.com/SYSTRAN/faster-whisper
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
