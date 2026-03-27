import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

@immutable
class KilterPalette extends ThemeExtension<KilterPalette> {
  const KilterPalette({
    required this.canvas,
    required this.mist,
    required this.panel,
    required this.panelRaised,
    required this.primary,
    required this.primaryGlow,
    required this.secondary,
    required this.highlight,
    required this.ink,
    required this.subtleInk,
    required this.stroke,
  });

  final Color canvas;
  final Color mist;
  final Color panel;
  final Color panelRaised;
  final Color primary;
  final Color primaryGlow;
  final Color secondary;
  final Color highlight;
  final Color ink;
  final Color subtleInk;
  final Color stroke;

  @override
  KilterPalette copyWith({
    Color? canvas,
    Color? mist,
    Color? panel,
    Color? panelRaised,
    Color? primary,
    Color? primaryGlow,
    Color? secondary,
    Color? highlight,
    Color? ink,
    Color? subtleInk,
    Color? stroke,
  }) {
    return KilterPalette(
      canvas: canvas ?? this.canvas,
      mist: mist ?? this.mist,
      panel: panel ?? this.panel,
      panelRaised: panelRaised ?? this.panelRaised,
      primary: primary ?? this.primary,
      primaryGlow: primaryGlow ?? this.primaryGlow,
      secondary: secondary ?? this.secondary,
      highlight: highlight ?? this.highlight,
      ink: ink ?? this.ink,
      subtleInk: subtleInk ?? this.subtleInk,
      stroke: stroke ?? this.stroke,
    );
  }

  @override
  KilterPalette lerp(ThemeExtension<KilterPalette>? other, double t) {
    if (other is! KilterPalette) {
      return this;
    }

    return KilterPalette(
      canvas: Color.lerp(canvas, other.canvas, t) ?? canvas,
      mist: Color.lerp(mist, other.mist, t) ?? mist,
      panel: Color.lerp(panel, other.panel, t) ?? panel,
      panelRaised: Color.lerp(panelRaised, other.panelRaised, t) ?? panelRaised,
      primary: Color.lerp(primary, other.primary, t) ?? primary,
      primaryGlow: Color.lerp(primaryGlow, other.primaryGlow, t) ?? primaryGlow,
      secondary: Color.lerp(secondary, other.secondary, t) ?? secondary,
      highlight: Color.lerp(highlight, other.highlight, t) ?? highlight,
      ink: Color.lerp(ink, other.ink, t) ?? ink,
      subtleInk: Color.lerp(subtleInk, other.subtleInk, t) ?? subtleInk,
      stroke: Color.lerp(stroke, other.stroke, t) ?? stroke,
    );
  }
}

KilterPalette kilterPaletteOf(BuildContext context) {
  return Theme.of(context).extension<KilterPalette>()!;
}

ThemeData buildAppTheme() {
  const KilterPalette palette = KilterPalette(
    canvas: Color(0xFFF1ECE2),
    mist: Color(0xFFE5E0D4),
    panel: Color(0xFFFFFCF7),
    panelRaised: Color(0xFFF7F0E4),
    primary: Color(0xFF23533F),
    primaryGlow: Color(0xFF8EB79B),
    secondary: Color(0xFF7A6E34),
    highlight: Color(0xFFC7682F),
    ink: Color(0xFF18211D),
    subtleInk: Color(0xFF5C675F),
    stroke: Color(0xFFD3CCBE),
  );

  final ColorScheme colorScheme = ColorScheme.fromSeed(
    seedColor: palette.primary,
    brightness: Brightness.light,
  ).copyWith(
    primary: palette.primary,
    onPrimary: Colors.white,
    secondary: palette.secondary,
    onSecondary: Colors.white,
    tertiary: palette.highlight,
    onTertiary: Colors.white,
    surface: palette.panel,
    onSurface: palette.ink,
    outline: palette.stroke,
    outlineVariant: palette.stroke.withValues(alpha: 0.7),
    shadow: palette.ink.withValues(alpha: 0.12),
    scrim: palette.ink.withValues(alpha: 0.3),
    surfaceContainerHighest: palette.panelRaised,
  );

  final TextTheme baseTextTheme = GoogleFonts.plusJakartaSansTextTheme(
    Typography.blackMountainView,
  );
  final TextTheme textTheme = baseTextTheme.copyWith(
    displayLarge: GoogleFonts.spaceGrotesk(
      fontSize: 42,
      fontWeight: FontWeight.w700,
      letterSpacing: -2.2,
      height: 0.96,
      color: palette.ink,
    ),
    headlineMedium: GoogleFonts.spaceGrotesk(
      fontSize: 28,
      fontWeight: FontWeight.w700,
      letterSpacing: -1.0,
      color: palette.ink,
    ),
    titleLarge: GoogleFonts.spaceGrotesk(
      fontSize: 21,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.5,
      color: palette.ink,
    ),
    titleMedium: GoogleFonts.plusJakartaSans(
      fontSize: 16,
      fontWeight: FontWeight.w700,
      color: palette.ink,
    ),
    bodyLarge: GoogleFonts.plusJakartaSans(
      fontSize: 16,
      height: 1.5,
      color: palette.ink,
    ),
    bodyMedium: GoogleFonts.plusJakartaSans(
      fontSize: 14,
      height: 1.45,
      color: palette.subtleInk,
    ),
    bodySmall: GoogleFonts.plusJakartaSans(
      fontSize: 12,
      height: 1.4,
      color: palette.subtleInk,
    ),
    labelLarge: GoogleFonts.plusJakartaSans(
      fontSize: 14,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.15,
      color: palette.ink,
    ),
    labelMedium: GoogleFonts.plusJakartaSans(
      fontSize: 12,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.2,
      color: palette.subtleInk,
    ),
    labelSmall: GoogleFonts.plusJakartaSans(
      fontSize: 11,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.3,
      color: palette.subtleInk,
    ),
  );

  final RoundedRectangleBorder largeShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(30),
  );
  final RoundedRectangleBorder mediumShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(22),
  );
  final RoundedRectangleBorder pillShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(999),
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: palette.canvas,
    splashFactory: InkSparkle.splashFactory,
    textTheme: textTheme,
    dividerColor: palette.stroke,
    cardTheme: CardThemeData(
      color: palette.panel,
      elevation: 0,
      margin: EdgeInsets.zero,
      surfaceTintColor: Colors.transparent,
      shape: largeShape.copyWith(
        side: BorderSide(color: palette.stroke),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: palette.primary,
        foregroundColor: Colors.white,
        disabledBackgroundColor: palette.primary.withValues(alpha: 0.35),
        disabledForegroundColor: Colors.white.withValues(alpha: 0.7),
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        textStyle: textTheme.labelLarge,
        shape: mediumShape,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: palette.ink,
        backgroundColor: palette.panel.withValues(alpha: 0.76),
        side: BorderSide(color: palette.stroke),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        textStyle: textTheme.labelLarge,
        shape: mediumShape,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: palette.primary,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        textStyle: textTheme.labelLarge,
        shape: pillShape,
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: palette.panelRaised,
      deleteIconColor: palette.subtleInk,
      disabledColor: palette.panelRaised.withValues(alpha: 0.5),
      secondarySelectedColor: palette.primary.withValues(alpha: 0.18),
      selectedColor: palette.primary.withValues(alpha: 0.18),
      side: BorderSide(color: palette.stroke),
      labelStyle: textTheme.labelMedium?.copyWith(color: palette.ink),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      shape: pillShape,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: palette.panel,
      surfaceTintColor: Colors.transparent,
      shape: largeShape,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: palette.panel,
      surfaceTintColor: Colors.transparent,
      shape: largeShape,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: palette.ink,
      contentTextStyle: textTheme.bodyMedium?.copyWith(color: Colors.white),
      behavior: SnackBarBehavior.floating,
      shape: mediumShape,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith<Color>(
        (Set<WidgetState> states) {
          if (states.contains(WidgetState.selected)) {
            return palette.primary;
          }
          return palette.subtleInk;
        },
      ),
      trackColor: WidgetStateProperty.resolveWith<Color>(
        (Set<WidgetState> states) {
          if (states.contains(WidgetState.selected)) {
            return palette.primaryGlow.withValues(alpha: 0.42);
          }
          return palette.stroke;
        },
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: palette.panel,
      labelStyle: textTheme.bodyMedium?.copyWith(color: palette.subtleInk),
      hintStyle: textTheme.bodyMedium?.copyWith(
        color: palette.subtleInk.withValues(alpha: 0.8),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: BorderSide(color: palette.stroke),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: BorderSide(color: palette.stroke),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: BorderSide(color: palette.primary, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: const BorderSide(color: Color(0xFF9B3445)),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(22),
        borderSide: const BorderSide(color: Color(0xFF9B3445), width: 1.5),
      ),
    ),
    dropdownMenuTheme: DropdownMenuThemeData(
      menuStyle: MenuStyle(
        backgroundColor: WidgetStatePropertyAll<Color>(palette.panel),
        shape: WidgetStatePropertyAll<OutlinedBorder>(largeShape),
      ),
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: palette.panel,
      surfaceTintColor: Colors.transparent,
      shape: largeShape,
    ),
    extensions: const <ThemeExtension<dynamic>>[
      palette,
    ],
  );
}
