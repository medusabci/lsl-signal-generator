# Signal generator

Generador de señal sintética (EEG simulado o ruido uniforme) que se transmite por red mediante [Lab Streaming Layer (LSL)](https://labstreaminglayer.org/). Sirve para probar [MEDUSA](https://www.medusabci.com/) y cualquier otro receptor LSL (LabRecorder, visores, scripts propios) sin necesidad de un amplificador real.

## Instalación

1. Descarga el instalador de la **[última release de GitHub](https://github.com/medusabci/lsl-signal-generator/releases/latest)** (`signal_generator_setup_<versión>.exe`) y ejecútalo.
   - Por defecto se instala solo para tu usuario, sin permisos de administrador. El asistente permite elegir una instalación para todos los usuarios.
   - Crea un acceso en el menú Inicio y, opcionalmente, en el escritorio.
   - Para actualizar, ejecuta el instalador de la versión nueva: sustituye a la instalada.
2. Abre **Signal generator**, ajusta los parámetros y pulsa **Start**.

No hace falta instalar Python ni ninguna dependencia.

## Uso

| Parámetro | Qué hace |
|---|---|
| Stream name / type | Nombre y tipo del stream LSL. Los receptores lo encuentran por el nombre. |
| Chunk size | Muestras que se envían juntas en cada envío (por defecto 16). No cambia la frecuencia de muestreo, solo la latencia y la carga de CPU. |
| Format | `float32`, `double64`, `int32` o `int16`. |
| Number of channels / Channel labels | Número de canales y sus etiquetas separadas por `;`. Al cambiar el número de canales (flechas, teclado o rueda del ratón) se rellenan con los nombres estándar 10-20 / 10-10. |
| Units | Unidades escritas en los metadatos (p. ej. `uV`). |
| Sample rate | Frecuencia de muestreo nominal. |
| Generator | `EEG (closed eyes)`: ruido rosa + tonos de 10 y 20 Hz. `EEG (open eyes)`: solo ruido rosa. `Uniform`: ruido blanco con media y desviación estándar configurables. En los EEG se puede añadir la interferencia de red de 50 Hz y su armónico de 100 Hz. |

- Los parámetros se bloquean mientras se transmite y se recuerdan entre sesiones.
- La barra inferior indica si hay transmisión, las muestras enviadas, la frecuencia efectiva y si algún receptor está leyendo el stream (LSL no indica cuál).
- Los errores y avisos quedan en `logs/` (junto al programa, o en `%LOCALAPPDATA%\SignalGenerator\logs` si esa carpeta no es escribible).

## Cómo se transmite

- **Frecuencia exacta.** Los chunks se envían contra un calendario absoluto (`inicio + k · chunk_size / fs`). El retardo de cada iteración no se acumula, de modo que la frecuencia efectiva es la nominal. Medido en la v2.4 con 4 canales, 250 Hz y chunk de 16 durante 40 s: 250,0000 Hz (≈ 0 ppm); la v2.3 daba 249,868 Hz (−528 ppm).
- **Sello temporal.** Cada chunk se sella con `local_clock()` en el momento del envío (como `gNEEDaccess.exe` y [signal-gtec](../signal-gtec)); LSL rellena hacia atrás las muestras anteriores con `1/fs`.
- **Señal precalculada.** Se genera antes de empezar (un bucle de unos 64 s, limitado a 64 MB; dura un número entero de segundos cuando es posible para que los tonos sean continuos al reiniciar el bucle) y se reproduce en bucle, así que el envío no depende del coste de generarla.
- **Metadatos.** Convenciones XDF/LSL: por canal `label`, `unit` (y `units`, por compatibilidad con la v2.3 y con la salida de MEDUSA) y `type`; además `manufacturer`, `acquisition` y `synchronization` (`can_drop_samples = false`). No se escribe `offset_mean`: no hay retardo de adquisición.
- **CPU.** Un único hilo de envío que duerme y solo espera activamente los últimos ~1,5 ms de cada chunk: ≈ 2 % de un núcleo con la configuración por defecto.

## Cambios de la v2.4

Encontrados al probar la v2.3 con lo aprendido en signal-gtec:

- **Corregido:** deriva de −528 ppm en la frecuencia (≈ 1,9 s por hora): el temporizador dormía `chunk_period` tras cada envío y acumulaba el coste de cada iteración.
- **Corregido:** 100 % de CPU en dos procesos (un temporizador y un hilo de envío que no dormían).
- **Corregido:** con 1 canal o con chunk de 1 muestra no llegaban datos (`np.squeeze`), y el cierre durante el envío podía dejar un hilo roto.
- **Corregido:** cada *Start* creaba un generador sin cerrar el anterior (hilos y procesos acumulados, y la aplicación no terminaba); cerrar la ventana sin haber arrancado lanzaba una excepción y no la cerraba; un fallo al crear el stream dejaba todo en marcha.
- **Corregido:** el ruido rosa «offline» acumulaba los tonos en su propio buffer al repetir el bucle.
- **Corregido:** el formato era texto libre (cualquier valor fallaba al arrancar), el tamaño de chunk y la frecuencia podían valer 0, y con muchos canales y chunks grandes el buffer podía pedir varios GB.
- **Corregido:** el programa reescribía los `.svg` de sus iconos (falla si se instala en una carpeta de solo lectura) y dependía del directorio de trabajo.
- **UX:** errores en diálogos (la notificación de 2 s cortaba el texto), validación antes de arrancar, etiquetas en rojo si no coinciden con los canales, tooltips, formato en lista desplegable, parámetros bloqueados mientras se transmite, estado informativo, la ventana no se congela mientras se genera la señal y se recuerdan los parámetros.
- **Nuevo:** metadatos XDF/LSL, estado del consumidor, registro en archivo, `version.py`, instalador con Inno Setup.
- **Dependencias:** se eliminan pandas y Pillow (ya no se usan).

## Compilar desde el código

Requisitos: Windows, Python 3.10, y [Inno Setup 6 o 7](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

Para ejecutar sin compilar:

```powershell
.\.venv\Scripts\python src\main.py
```

Para generar el instalador:

```powershell
.\build_release.ps1
```

Deja el resultado en `release\signal_generator_setup_<versión>.exe`. La versión se define en un único sitio, `src/version.py`. Opciones: `-SkipBuild` (reutiliza `dist\` y solo recompila el instalador) y `-SkipInstaller` (solo PyInstaller).

## Estructura

| Ruta | Contenido |
|---|---|
| `src/main.py` | Ventana principal |
| `src/signal_generator.py` | Generadores de señal y transmisión LSL |
| `src/logging_setup.py` | Registro en archivo, excepciones y errores nativos |
| `src/version.py` | Versión de la aplicación |
| `src/gui/` | Estilo, tema, iconos y utilidades de la interfaz |
| `installer/signal_generator.iss` | Script de Inno Setup |
| `build_release.ps1` | Compilación y empaquetado |

## Autores

Víctor Martínez-Cagigal y Eduardo Santamaría-Vázquez (GIB-UVa).
