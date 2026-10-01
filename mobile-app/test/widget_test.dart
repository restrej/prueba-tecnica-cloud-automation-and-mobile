// =============================================================================
// Pruebas de WIDGETS de PickApp (nivel unit/componente del lado Flutter).
//
// Corren sin emulador (`flutter test`), en segundos. Son la primera red de
// seguridad; Appium (E2E) cubre después el flujo en un dispositivo real.
// =============================================================================

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pickapp/main.dart';

/// Hace login con las credenciales indicadas.
Future<void> login(WidgetTester tester, String user, String password) async {
  // pumpWidget: dibuja la app.
  await tester.pumpWidget(const PickApp());
  // enterText escribe en el primer y segundo TextField (usuario, contraseña).
  await tester.enterText(find.byType(TextField).at(0), user);
  await tester.enterText(find.byType(TextField).at(1), password);
  await tester.tap(find.text('Ingresar'));
  // pumpAndSettle: espera a que terminen animaciones/navegación.
  await tester.pumpAndSettle();
}

/// Simula un escaneo: escribe el código y presiona ENTER (como un lector físico).
Future<void> scan(WidgetTester tester, String barcode) async {
  await tester.enterText(find.byType(TextField), barcode);
  await tester.testTextInput.receiveAction(TextInputAction.done);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('credenciales inválidas muestran error', (tester) async {
    await login(tester, 'OP-312', 'mala');
    expect(find.text('Credenciales inválidas'), findsOneWidget);
  });

  testWidgets('happy path domicilio: escaneo completo genera guía', (tester) async {
    await login(tester, 'OP-312', 'Pick2025!');
    expect(find.text('Pedidos asignados'), findsOneWidget);
    await tester.tap(find.text('ORD-2025-007841'));
    await tester.pumpAndSettle();
    await scan(tester, '7501234567890');
    await scan(tester, '7501234567891');
    expect(find.text('Escaneados: 2/2'), findsOneWidget);
    await tester.tap(find.text('Confirmar preparación'));
    await tester.pumpAndSettle();
    expect(find.text('Guía Generada'), findsOneWidget);
    expect(find.text('Guía: GUIA-2025-007841'), findsOneWidget);
  });

  testWidgets('recogida en tienda termina en Listo para recoger', (tester) async {
    await login(tester, 'OP-312', 'Pick2025!');
    await tester.tap(find.text('ORD-2025-007842'));
    await tester.pumpAndSettle();
    await scan(tester, '7501234567892');
    await tester.tap(find.text('Confirmar preparación'));
    await tester.pumpAndSettle();
    expect(find.text('Listo para recoger'), findsOneWidget);
  });

  testWidgets('código que no pertenece al pedido muestra error', (tester) async {
    await login(tester, 'OP-312', 'Pick2025!');
    await tester.tap(find.text('ORD-2025-007841'));
    await tester.pumpAndSettle();
    await scan(tester, '0000000000000');
    expect(find.text('Producto 0000000000000 no pertenece al pedido'), findsOneWidget);
    expect(find.text('Escaneados: 0/2'), findsOneWidget);
  });

  testWidgets('rechazo deja el pedido pendiente de resurtido', (tester) async {
    await login(tester, 'OP-312', 'Pick2025!');
    await tester.tap(find.text('ORD-2025-007841'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Rechazar: producto no disponible'));
    await tester.pumpAndSettle();
    expect(find.text('Pendiente de resurtido'), findsOneWidget);
  });
}
