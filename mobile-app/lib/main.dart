// =============================================================================
// PickApp DEMO (Flutter) - objetivo de las pruebas mobile con Appium.
//
// Flujo: Login -> Lista de pedidos -> Detalle de productos -> Escanear
//        -> Confirmar preparación -> Guía generada / Listo para recoger / Rechazo.
//
// CLAVE PARA AUTOMATIZACIÓN:
// Flutter dibuja la interfaz en un lienzo propio; Appium NO ve los widgets
// directamente, sólo el árbol de ACCESIBILIDAD (semantics). Por eso cada
// elemento importante se envuelve en `Semantics(identifier: '...')`:
//   - En Android ese identifier aparece como `resource-id`.
//   - En iOS aparece como `accessibilityIdentifier`.
// Es el equivalente móvil del `data-testid` de la web: un locator estable.
// =============================================================================

import 'package:flutter/material.dart';

import 'data.dart';

/// Punto de entrada de la app.
void main() => runApp(const PickApp());

/// Envuelve un widget con un identificador estable para Appium.
Widget testId(String id, Widget child) => Semantics(identifier: id, child: child);

/// Widget raíz: configura el tema y la primera pantalla (login).
class PickApp extends StatelessWidget {
  /// Constructor constante (Flutter puede reutilizar la instancia).
  const PickApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PickApp',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      home: const LoginScreen(),
    );
  }
}

// -----------------------------------------------------------------------------
// 1. LOGIN
// -----------------------------------------------------------------------------

/// Pantalla de inicio de sesión del operador.
class LoginScreen extends StatefulWidget {
  /// Constructor.
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  // Controladores: guardan el texto escrito en cada campo.
  final _userController = TextEditingController();
  final _passwordController = TextEditingController();
  // Mensaje de error visible (null = sin error).
  String? _error;

  /// Valida credenciales y navega a la lista de pedidos.
  void _login() {
    final user = _userController.text.trim();
    final password = _passwordController.text;
    if (user.isEmpty || password.isEmpty) {
      setState(() => _error = 'Ingresa usuario y contraseña');
      return;
    }
    if (user != demoOperatorUser || password != demoOperatorPassword) {
      setState(() => _error = 'Credenciales inválidas');
      return;
    }
    // pushReplacement: reemplaza el login (el botón "atrás" no vuelve a él).
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => OrdersScreen(orders: buildDemoOrders())),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('PickApp - Iniciar sesión')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            testId('login-username', TextField(
              controller: _userController,
              decoration: const InputDecoration(labelText: 'Usuario'),
            )),
            testId('login-password', TextField(
              controller: _passwordController,
              obscureText: true, // oculta la contraseña
              decoration: const InputDecoration(labelText: 'Contraseña'),
            )),
            const SizedBox(height: 24),
            testId('login-button', FilledButton(onPressed: _login, child: const Text('Ingresar'))),
            if (_error != null)
              testId('login-error', Text(_error!, style: const TextStyle(color: Colors.red))),
          ],
        ),
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// 2. LISTA DE PEDIDOS ASIGNADOS
// -----------------------------------------------------------------------------

/// Lista de pedidos asignados al operador.
class OrdersScreen extends StatelessWidget {
  /// Recibe los pedidos a mostrar.
  const OrdersScreen({super.key, required this.orders});

  /// Pedidos asignados.
  final List<Order> orders;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: testId('orders-title', const Text('Pedidos asignados'))),
      body: ListView(
        children: [
          for (final order in orders)
            testId('order-${order.id}', ListTile(
              title: Text(order.id),
              subtitle: Text('${order.items.length} producto(s) - '
                  '${order.deliveryType == DeliveryType.homeDelivery ? 'Envío a domicilio' : 'Recogida en tienda'}'),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => OrderDetailScreen(order: order)),
              ),
            )),
        ],
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// 3. DETALLE + ESCANEO + CONFIRMACIÓN
// -----------------------------------------------------------------------------

/// Detalle del pedido: productos, escaneo y confirmación.
class OrderDetailScreen extends StatefulWidget {
  /// Recibe el pedido seleccionado.
  const OrderDetailScreen({super.key, required this.order});

  /// Pedido en preparación.
  final Order order;

  @override
  State<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<OrderDetailScreen> {
  final _scanController = TextEditingController();
  // FocusNode: mantiene el foco en el campo de escaneo (los lectores
  // "keyboard wedge" escriben donde esté el foco, como un teclado).
  final _scanFocus = FocusNode();
  String? _scanError;

  /// Procesa un código escaneado (desde scanner físico, cámara o teclado manual).
  void _onScan(String code) {
    final barcode = code.trim();
    // Buscamos el producto con ese código de barras dentro del pedido.
    final matches = widget.order.items.where((item) => item.barcode == barcode);
    setState(() {
      if (barcode.isEmpty) {
        _scanError = 'Código vacío, vuelve a escanear';
      } else if (matches.isEmpty) {
        _scanError = 'Producto $barcode no pertenece al pedido';
      } else if (matches.first.scanned) {
        _scanError = 'Producto ${matches.first.sku} ya fue escaneado';
      } else {
        matches.first.scanned = true;
        _scanError = null;
      }
    });
    // Limpiamos el campo y devolvemos el foco para el siguiente escaneo.
    _scanController.clear();
    _scanFocus.requestFocus();
  }

  /// Navega a la pantalla de resultado con el estado final del pedido.
  void _finish(String status, {String? guide}) {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ResultScreen(orderId: widget.order.id, status: status, guide: guide)),
    );
  }

  /// Confirma la preparación: domicilio genera guía; tienda queda "Listo para recoger".
  void _confirm() {
    if (widget.order.deliveryType == DeliveryType.homeDelivery) {
      _finish('Guía Generada', guide: 'GUIA-${widget.order.id.substring(4)}');
    } else {
      _finish('Listo para recoger');
    }
  }

  @override
  Widget build(BuildContext context) {
    final order = widget.order;
    return Scaffold(
      appBar: AppBar(title: testId('detail-title', Text(order.id))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final item in order.items)
            testId('item-${item.sku}', ListTile(
              title: Text('${item.sku} - ${item.name}'),
              trailing: Text(item.scanned ? 'Escaneado' : 'Pendiente'),
            )),
          testId('scan-progress', Text('Escaneados: ${order.scannedCount}/${order.items.length}')),
          testId('scan-input', TextField(
            controller: _scanController,
            focusNode: _scanFocus,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Escanear o digitar código'),
            // onSubmitted se dispara con ENTER: los scanners envían ENTER al final del código.
            onSubmitted: _onScan,
          )),
          if (_scanError != null)
            testId('scan-error', Text(_scanError!, style: const TextStyle(color: Colors.red))),
          const SizedBox(height: 16),
          testId('confirm-button', FilledButton(
            // Deshabilitado (null) hasta escanear todo: evita despachar pedidos incompletos.
            onPressed: order.isComplete ? _confirm : null,
            child: const Text('Confirmar preparación'),
          )),
          testId('reject-button', TextButton(
            onPressed: () => _finish('Pendiente de resurtido'),
            child: const Text('Rechazar: producto no disponible'),
          )),
        ],
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// 4. RESULTADO
// -----------------------------------------------------------------------------

/// Pantalla final con el estado del pedido y, si aplica, la guía de envío.
class ResultScreen extends StatelessWidget {
  /// Recibe el pedido, su estado final y la guía (opcional).
  const ResultScreen({super.key, required this.orderId, required this.status, this.guide});

  /// ID del pedido.
  final String orderId;

  /// Estado final: "Guía Generada", "Listo para recoger" o "Pendiente de resurtido".
  final String status;

  /// Número de guía (sólo envío a domicilio).
  final String? guide;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(orderId)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            testId('order-status', Text(status, style: const TextStyle(fontSize: 22))),
            if (guide != null) testId('guide-number', Text('Guía: $guide')),
          ],
        ),
      ),
    );
  }
}
