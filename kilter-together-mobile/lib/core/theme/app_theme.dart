import 'package:flutter/material.dart';

ThemeData buildAppTheme() {
  const Color seed = Color(0xFF0F766E);
  final ColorScheme colorScheme = ColorScheme.fromSeed(
    seedColor: seed,
    brightness: Brightness.light,
    primary: seed,
    secondary: const Color(0xFF84CC16),
    surface: Colors.white,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: const Color(0xFFF4FBFA),
    textTheme: Typography.blackMountainView.copyWith(
      displayLarge: const TextStyle(
        fontSize: 38,
        fontWeight: FontWeight.w800,
        letterSpacing: -1.4,
      ),
      headlineMedium: const TextStyle(
        fontSize: 26,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.6,
      ),
      titleLarge: const TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.w700,
      ),
      bodyLarge: const TextStyle(
        fontSize: 16,
        height: 1.35,
      ),
    ),
    cardTheme: const CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(28)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(20),
        borderSide: const BorderSide(color: Color(0xFFB7E4DF)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(20),
        borderSide: const BorderSide(color: Color(0xFFB7E4DF)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(20),
        borderSide: const BorderSide(color: Color(0xFF0F766E), width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
    ),
  );
}

