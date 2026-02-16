# Frontend Features Documentation

## Overview

The cAI-png v2.0 frontend has been completely redesigned with modern UI/UX patterns, enhanced visualizations, and improved user experience while maintaining the lightweight React architecture.

## New Features

### 🎨 Modern UI Design

- **Gradient Background**: Beautiful purple gradient backdrop
- **Glass-morphism Effects**: Translucent header with backdrop blur
- **Card-based Layout**: Clean, organized content with shadow effects
- **Smooth Animations**: Transitions, hover effects, and micro-interactions
- **Responsive Design**: Mobile-optimized layout that adapts to all screen sizes

### 🌙 Dark Mode

- Toggle between light and dark themes
- Persistent across sessions
- Smooth theme transitions
- Accessible color contrasts

### 💚 Health Status Indicator

- Real-time backend health monitoring
- Visual status indicators (🟢 OK, 🟠 Degraded, 🔴 Error, 🟡 Checking)
- Auto-refresh every 30 seconds
- Hover tooltip with status message
- Uses `/health` endpoint

### 📊 Enhanced Macro Visualization

Instead of raw JSON, macros are displayed as:
- **Visual Cards**: Four macro cards with icons
  - 🔥 Calories (kcal)
  - 💪 Protein (g)
  - 🌾 Carbs (g)
  - 🥑 Fat (g)
- **Large Numbers**: Easy-to-read values
- **AI Narrative**: Natural language explanation below macros
- **Gradient Backgrounds**: Visual hierarchy

### 🎯 Food Detection Panel

- **Emoji Icons**: Visual food type indicators
  - 🥬 Vegetables
  - 🍗 Protein
  - 🍚 Starch/Rice
  - 🍽️ Other
- **Progress Bars**: Visual confidence indicators
- **Weight Display**: Gram estimates for each detected item
- **Hover Effects**: Cards expand slightly on hover
- **Color Coding**: Matches bounding box colors

### 📜 History Tracking

- **Session History**: Stores last 5 nutrition analyses
- **Timestamp**: When each analysis was performed
- **Quick Summary**: Calories + detected foods
- **Persistent**: Maintains history during session
- **Visual Timeline**: Color-coded entries

### ⚙️ Settings Panel

Collapsible settings with:
- **Frame Rate Control**: Choose detection speed
  - ~4 FPS (Slower, saves resources)
  - ~6-7 FPS (Balanced, default)
  - ~10 FPS (Faster, more responsive)
- **Local Detection Toggle**: Switch between ML and color-based detection
- **Smooth Animations**: Slide-down panel appearance

### 📹 Enhanced Video Controls

- **FPS Counter**: Real-time frames-per-second display
- **Large Control Buttons**: 
  - ▶️ Start Detection (green gradient)
  - ⏸️ Pause Detection (orange gradient)
  - 🍽️ Estimate Nutrition (blue gradient)
- **Loading States**: Animated loading for async operations
- **Disabled States**: Visual feedback when actions unavailable
- **Compact Legend**: Food category legend in video card header

### 🎬 Video Feed Improvements

- **Aspect Ratio**: Maintains 4:3 aspect ratio
- **Rounded Corners**: Modern card appearance
- **Overlay Message**: "Press Start" prompt when inactive
- **Better Error Display**: Friendly camera error messages with retry button
- **Professional Layout**: Header with title and legend

### 📱 Mobile Responsive

- **Flexible Grid**: Switches from 2-column to 1-column on tablets
- **Touch-Friendly**: Larger buttons on mobile
- **Compact Header**: Stacks header elements vertically on small screens
- **Readable Text**: Scales font sizes appropriately
- **Full-width Controls**: Control buttons expand on mobile

## Technical Details

### Performance Optimizations

- **Throttled FPS Counter**: Updates once per second
- **Efficient Re-renders**: Uses refs for non-visual state
- **Lazy Animations**: CSS transitions instead of JavaScript
- **Optimized Images**: JPEG compression at 0.7 quality

### Accessibility

- **ARIA Labels**: Proper labels for screen readers
- **Keyboard Navigation**: All controls keyboard accessible
- **Color Contrast**: Meets WCAG AA standards
- **Focus Indicators**: Visible focus states

### Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Requires WebRTC for camera access
- CSS Grid and Flexbox support
- CSS Custom Properties (CSS Variables)

## Usage Examples

### Starting Detection

1. Click "▶️ Start Detection"
2. Watch real-time bounding boxes appear
3. View detected foods in right panel
4. Monitor FPS in top-right corner

### Getting Nutrition Info

1. Ensure detection is running or has run
2. Click "🍽️ Estimate Nutrition"
3. Wait for AI analysis (2-5 seconds)
4. View macro cards and narrative
5. Check history panel for saved results

### Adjusting Settings

1. Click ⚙️ settings icon
2. Adjust frame rate for performance
3. Toggle local detection for offline use
4. Click outside panel to close

### Switching Themes

1. Click 🌙/☀️ button in header
2. Theme switches immediately
3. All colors update smoothly

## Backend Endpoints Used

All three available endpoints are fully integrated:

1. **GET /health**
   - Called: On mount + every 30 seconds
   - Purpose: Monitor server status
   - Display: Header indicator

2. **POST /api/live/analyze**
   - Called: Every frame during detection
   - Purpose: ML-based food detection
   - Display: Bounding boxes + food list

3. **POST /api/live/macros**
   - Called: On "Estimate Nutrition" click
   - Purpose: AI nutrition analysis
   - Display: Macro cards + narrative + history

## Styling Architecture

### CSS Variables

All colors defined as CSS custom properties for:
- Easy theming
- Consistent design system
- Dark mode support
- Quick customization

### Component Styles

- **No CSS-in-JS libraries**: Pure CSS + inline React styles
- **Class-based**: Reusable CSS classes
- **BEM-inspired**: Logical naming conventions
- **Scoped**: Component-specific classes

### Animations

- **CSS Transitions**: Smooth property changes
- **Keyframe Animations**: Pulse, slide-down effects
- **Transform**: Hardware-accelerated animations
- **Cubic Bezier**: Custom easing functions

## Future Enhancements

Potential additions:
- 📸 Screenshot/download capability
- 📤 Share results feature
- 📈 Multi-day tracking charts
- 🎯 Daily macro goals
- 🔔 Notification system
- 💾 Local storage persistence
- 🗺️ Food map visualization
- 🔍 Search through history

## Browser DevTools Tips

### Check Health Status
```javascript
fetch('http://localhost:5000/health').then(r => r.json()).then(console.log)
```

### Monitor FPS
Watch the FPS badge in the top-right corner during detection

### View History
React DevTools → LiveView component → history state

### Debug Detection
Enable "Preserve log" in Console to see all API calls
