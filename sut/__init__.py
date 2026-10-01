"""
Paquete ``sut`` (System Under Test).

LogiTrack es una empresa ficticia, por lo que no existe un backend real contra el
cual ejecutar las pruebas. Este paquete implementa una versión SIMULADA y reducida
del microservicio ``orders-api`` (y de la pantalla de login del Centro de Control)
con el único fin de que todas las pruebas del repositorio sean EJECUTABLES.

Componentes:
    - ``config``      -> lectura de configuración desde variables de entorno.
    - ``errors``      -> jerarquía de errores de dominio (404, 409, 422...).
    - ``security``    -> tokens JWT, roles, hash de contraseñas y rate limiting.
    - ``data``        -> datos semilla (usuarios, operadores, almacenes, pedidos).
    - ``repository``  -> almacenamiento en memoria (simula Cloud SQL).
    - ``events``      -> bus de eventos en memoria (simula Google Pub/Sub).
    - ``service``     -> lógica de negocio de asignación de pedidos.
    - ``schemas``     -> modelos de entrada/salida validados con Pydantic.
    - ``main``        -> aplicación FastAPI: rutas, middlewares y manejadores de error.
"""
