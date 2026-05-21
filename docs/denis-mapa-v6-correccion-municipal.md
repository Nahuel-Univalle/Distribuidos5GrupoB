# Corrección mapa v6 - Denis

## Qué corrige

- Las burbujas y puntos de medidores ahora usan una normalización municipal para que caigan visualmente en el distrito y subdistrito/zona oficial correspondiente.
- La capa de rectángulos simulados SEMAPA queda apagada por defecto para no confundirse con límites oficiales.
- Las capas oficiales WMS del Mapa Digital Municipal quedan visibles/ocultables desde el botón **Capas**.
- El mapa prioriza la visualización oficial: WMS de distritos + límite Cercado + puntos/burbujas SEMAPA.
- En el popup se muestra **Distrito municipal** y, cuando hay diferencia con el Excel, también se muestra **Registro base Excel**.

## Por qué era necesario

El Excel de la práctica trae 54 filas de distribución, con algunas zonas repetidas en más de un distrito para fines de poblamiento. En cambio, la división municipal consultada trabaja con 6 comunas, 15 distritos y zonas/subdistritos oficiales. Por eso algunas burbujas parecían caer fuera de su distrito cuando se comparaban contra la capa WMS oficial.

## Ejemplo importante

La zona **PUKARA GRANDE SUR / Subdistrito 35** corresponde al **Distrito 9 - Comuna Itocta** en la referencia municipal. Si aparece en el Excel como otro distrito, el frontend ahora la muestra en el distrito municipal correcto y conserva el dato base como referencia.

## Fuentes usadas

- Mapa Digital de Cochabamba: capas WMS/MapCache de distritos, comunas, subdistritos, manzanas, área urbana y límite Cercado.
- Lista territorial pública de comunas, distritos y zonas de Cochabamba.
