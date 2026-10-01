// =============================================================================
// Datos de ejemplo de la app demo PickApp.
//
// La app real consultaría orders-api; esta versión DEMO trabaja con datos
// locales para poder ejecutarse sin backend y ser automatizada con Appium.
// =============================================================================

/// Tipo de entrega del pedido: define cómo termina el flujo de preparación.
enum DeliveryType { homeDelivery, storePickup }

/// Un producto (SKU) dentro de un pedido.
class OrderItem {
  /// Crea un producto con su SKU, nombre y código de barras.
  OrderItem({required this.sku, required this.name, required this.barcode});

  /// Identificador del producto (ej. SKU-1001).
  final String sku;

  /// Nombre visible del producto.
  final String name;

  /// Código de barras EAN-13 que el operador escanea.
  final String barcode;

  /// Indica si ya fue escaneado en la preparación actual.
  bool scanned = false;
}

/// Un pedido asignado al operador.
class Order {
  /// Crea un pedido con su ID, tipo de entrega y productos.
  Order({required this.id, required this.deliveryType, required this.items});

  /// ID del pedido (ej. ORD-2025-007841).
  final String id;

  /// Envío a domicilio o recogida en tienda.
  final DeliveryType deliveryType;

  /// Productos que se deben escanear.
  final List<OrderItem> items;

  /// Cantidad de productos ya escaneados.
  int get scannedCount => items.where((item) => item.scanned).length;

  /// `true` cuando todos los productos fueron escaneados.
  bool get isComplete => scannedCount == items.length;
}

/// Credenciales válidas de la demo (operador OP-312).
const demoOperatorUser = 'OP-312';

/// Contraseña de la demo.
const demoOperatorPassword = 'Pick2025!';

/// Construye la lista de pedidos asignados de la demo (datos frescos cada vez).
List<Order> buildDemoOrders() => [
      Order(
        id: 'ORD-2025-007841',
        deliveryType: DeliveryType.homeDelivery,
        items: [
          OrderItem(sku: 'SKU-1001', name: 'Licuadora 600W', barcode: '7501234567890'),
          OrderItem(sku: 'SKU-2002', name: 'Juego de sartenes', barcode: '7501234567891'),
        ],
      ),
      Order(
        id: 'ORD-2025-007842',
        deliveryType: DeliveryType.storePickup,
        items: [
          OrderItem(sku: 'SKU-3003', name: 'Audífonos BT', barcode: '7501234567892'),
        ],
      ),
    ];
