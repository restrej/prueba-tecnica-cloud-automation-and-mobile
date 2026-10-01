# Parte 7. Comunicación y presentación de resultados

Datos: 3 meses · pruebas manuales en 5 módulos · 40 casos automatizados · 23 defectos (3 críticos, 8 altos, 12 medios) ·
35% de la regresión automatizada.

## 7.1 Estructura del informe ejecutivo de avance

**1. Resumen ejecutivo (1 diapositiva).** Semáforo general: 🟡 **AMARILLO: no listo para producción.**
Tres mensajes: (a) se encontraron y gestionaron 23 defectos antes de llegar al cliente, (b) quedan 3 críticos que
bloquean el release, (c) la automatización cubre 35% de la regresión y apunta a 70% en 3 meses.

**2. Alcance y avance.**

| Indicador | Valor | Visualización sugerida |
|---|---|---|
| Módulos probados manualmente | 5 de 9 (56%) | Barra de progreso por módulo |
| Casos automatizados | 40 | Línea de tendencia semanal (acumulado) |
| Cobertura de regresión automatizada | 35% (meta trimestral 70%) | Gauge / *bullet chart* con meta |
| Tiempo de regresión | manual ≈ 3 días → automatizado ≈ 25 min para el 35% | Barras comparativas |

**3. Estado de calidad del producto.**

| Severidad | Defectos encontrados | % del total |
|---|---|---|
| Crítico | 3 | 13% |
| Alto | 8 | 35% |
| Medio | 12 | 52% |
| **Total** | **23** | 100% |

Visualizaciones: barras apiladas por severidad y estado (abierto/en curso/cerrado) y heatmap **módulo × severidad**
para mostrar dónde se concentra el riesgo.

Más: tendencia de defectos abiertos vs cerrados (*burn-down*), defect leakage, tiempo medio de corrección por severidad.

**¿Está listo para producción?** **No todavía.** Criterios de salida propuestos: 0 críticos abiertos, ≤ 2 altos con
*workaround* aprobado por negocio, 100% de los flujos críticos (pedido → asignación → escaneo → guía) en verde,
regresión automatizada de flujos críticos en verde en 3 ejecuciones consecutivas, prueba de carga al +40% aprobada.
**Qué falta:** corregir y re-probar los 3 críticos, probar los 4 módulos restantes (incluidos Despacho y Alertas),
primera prueba de rendimiento y escaneo de seguridad.

**4. Riesgos y mitigación.**

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| 3 defectos críticos sin corregir para la fecha | Media | Alto | Priorizar en el sprint actual; *daily* de seguimiento; re-test el mismo día |
| 4 módulos sin probar | Alta | Alto | Plan de pruebas basado en riesgo: Despacho y Login primero |
| Sin pruebas de rendimiento ni seguridad | Alta | Alto | k6 y ZAP ya integrados en el pipeline (ver 3.3); ejecución completa en 2 semanas |
| Errores intermitentes del escáner | Media | Alto | Sesión en almacén con dispositivos reales + pruebas de simulación de escaneo |
| 65% de la regresión aún manual | Alta | Medio | Roadmap de automatización priorizado por riesgo |

**5. Próximos pasos y estimaciones.**

| Acción | Esfuerzo | Fecha objetivo |
|---|---|---|
| Re-test de los 3 críticos + regresión | 3 días | Semana 1 |
| Pruebas manuales de los 4 módulos restantes | 2 semanas | Semana 3 |
| Automatizar 30 casos más (→ ~55% de regresión) | 4 semanas | Semana 6 |
| Baseline de rendimiento (carga + spike) y DAST completo | 1 semana | Semana 2 |
| Quality gates obligatorios en el pipeline | 1 semana | Semana 2 |
| Meta: 70% de regresión automatizada | 3 meses | Mes 6 |

**6. Decisiones que se piden al liderazgo:** aprobar los criterios de salida, priorizar los críticos y asignar
dispositivos/escáneres para el laboratorio de pruebas.

**Formato:** 6–8 diapositivas + anexo; dashboard vivo (Looker Studio/Grafana alimentado por Jira, GitHub Actions y
Cloud Monitoring) para que el informe no sea una foto estática.

## 7.2 Respuesta al Gerente de Operaciones (≤ 200 palabras)

> **¿Por qué invertir en automatización si ya tenemos gente que prueba manualmente?**
>
> Porque el equipo manual no alcanza el ritmo del negocio. Publicamos cambios continuamente y hoy revisar a mano
> todo lo que ya funcionaba toma unos tres días; por eso se revisa solo una parte y los errores llegan a los almacenes.
>
> Un ejemplo de este proyecto: si un cambio vuelve a permitir que un pedido se asigne a dos operadores, hoy lo
> descubrimos cuando dos personas preparan el mismo pedido y otro cliente queda sin atender. Con automatización,
> esa verificación corre sola en minutos, en cada cambio y antes de llegar al almacén.
>
> La automatización no reemplaza a las personas: hace las verificaciones repetitivas para que el equipo se concentre
> en lo que requiere criterio humano, como probar con escáneres reales en el almacén.
>
> Retorno esperado: automatizar el 70% de la regresión libera alrededor de 15 días-persona por mes. Con una
> inversión inicial de unos tres meses, se recupera en aproximadamente seis meses, sin contar el ahorro más
> importante: menos pedidos retrasados, reprocesos y reclamos de clientes.

*(167 palabras)*
