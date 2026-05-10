# AsdeSim Qt Version

## 🎉 What's New

The Qt version brings a **professional, modern UI** to AsdeSim while keeping the powerful Pygame simulation engine intact!

## 🚀 Quick Start

**Run the Qt version:**
```bash
py -3.12 main_qt.py
```

**Compare with original:**
```bash
py -3.12 -m main  # Original Pygame version
```

## ✨ Features

### Professional UI
- **Native Windows interface** with menu bar, toolbar, and status bar
- **Dark theme** optimized for ATC operations
- **Dockable panels** - rearrange to your preference
- **Keyboard shortcuts** - Space (pause), F11 (fullscreen)

### Radio Panel (Bottom)
- ✅ Terminal-style display with timestamps
- ✅ Color-coded: Green (ATC), Blue (Aircraft)
- ✅ Auto-scroll to latest transmission
- ✅ Frequency selector (Ground, Tower, Departure, Approach)
- ✅ Only shows Ground frequency communications (121.9)

### Aircraft Panel (Right)
- ✅ Live table of all active aircraft
- ✅ Shows: Callsign, Type, State, Speed, Heading
- ✅ Color-coded states (Green=Takeoff, Yellow=Holding, Cyan=Taxi)
- ✅ Auto-refreshes every second
- ✅ Click to select aircraft (future feature)

### Simulation Display (Center)
- ✅ Full Pygame ASDE display at 60 FPS
- ✅ All existing features work (aircraft, runways, taxiways)
- ✅ Mouse and keyboard input forwarded from Qt
- ✅ Smooth, no performance loss

## 📐 Layout

```
┌────────────────────────────────────────────────────────────┐
│  File  Simulation  View  Help          [⏸] [🐌] [▶️] [⏩]  │ Menu/Toolbar
├─────────────────────────────────────────┬──────────────────┤
│                                         │  Aircraft Panel  │
│                                         │  ┌─────────────┐ │
│         Pygame Simulation               │  │ AAL123      │ │
│         (ASDE Display)                  │  │ B738        │ │
│                                         │  │ TAXI        │ │
│         60 FPS embedded                 │  │ 15 kts      │ │
│         in Qt widget                    │  │ 270°        │ │
│                                         │  └─────────────┘ │
│                                         │                  │
├─────────────────────────────────────────┴──────────────────┤
│  Radio Communications                                      │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ [12:34:56] [ATC] AAL123, taxi via Alpha              │ │
│  │ [12:34:58] [ACFT] AAL123, taxi Alpha                 │ │
│  └──────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────┤
│  Aircraft: 5 | FPS: 60 | ▶ RUNNING                        │ Status Bar
└────────────────────────────────────────────────────────────┘
```

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Space** | Pause/Resume simulation |
| **F11** | Toggle fullscreen |
| **Ctrl+N** | New simulation |
| **Ctrl+Q** | Quit |

## 🎛️ Menu Bar

### File
- New Simulation
- Exit

### Simulation
- Pause/Resume
- Simulation Speed (0.5x, 1x, 2x, 4x)

### View
- Toggle Radio Panel
- Toggle Aircraft Panel
- Fullscreen

### Help
- About

## 🔧 Architecture

```
Qt Application (PySide6)
├── Main Window (QMainWindow)
│   ├── Menu Bar
│   ├── Toolbar
│   ├── Simulation Widget ← Embeds Pygame Surface
│   ├── Radio Panel (QDockWidget)
│   ├── Aircraft Panel (QDockWidget)
│   └── Status Bar
│
Pygame Simulation (Background)
├── SimulationScreen (existing code)
│   ├── Aircraft Manager
│   ├── ATC Controllers
│   ├── Weather System
│   └── Rendering Engine
```

## 🔄 Migration Status

### ✅ Completed
- [x] Pygame embedded in Qt widget
- [x] Radio communications panel
- [x] Aircraft information panel
- [x] Professional menu and toolbar
- [x] Dark theme
- [x] Keyboard shortcuts
- [x] Status bar with live info
- [x] Pause/resume functionality
- [x] Tower frequency filtering

### 🚧 In Progress
- [ ] Settings dialog
- [ ] Airport selection menu
- [ ] Splash screen
- [ ] Custom icons
- [ ] Chart/graph widgets

### 📋 Future Enhancements
- [ ] Multiple display modes (split view)
- [ ] Flight strip bay
- [ ] Weather panel
- [ ] Traffic flow charts
- [ ] Replay system
- [ ] Save/load scenarios

## 🐛 Known Issues

1. **First run may be slower** - Qt initialization takes a moment
2. **Window resize** - Pygame surface scales but may have slight delay
3. **Mouse events** - Some Pygame mouse interactions need refinement

## 💡 Tips

**Customize Layout:**
- Drag dock widgets to rearrange
- Double-click dock title to float
- Right-click dock to close

**Performance:**
- Keep to 60 FPS for smooth simulation
- Dock widgets can be hidden for more screen space
- Fullscreen mode (F11) for maximum immersion

**Radio Panel:**
- Currently shows Ground frequency only (121.9)
- Tower transmissions filtered out (they're on 118.x)
- Use frequency selector to switch (future feature)

## 🤝 Comparison with Original

| Feature | Original (Pygame) | Qt Version |
|---------|------------------|------------|
| **UI Framework** | Pure Pygame | PySide6 + Pygame |
| **Menu System** | Custom rendered | Native Windows menu |
| **Controls** | Buttons rendered in Pygame | Qt native widgets |
| **Performance** | 60 FPS | 60 FPS (same) |
| **Appearance** | Custom theme | Professional dark theme |
| **Extensibility** | Manual widget code | Qt Designer compatible |
| **Radio Display** | Basic text overlay | Rich terminal-style panel |
| **Aircraft List** | Not visible | Live updating table |

## 📚 Development

**File Structure:**
```
src/ui/
├── __init__.py
├── main_window.py       # Main Qt window
├── simulation_widget.py # Pygame embedding
├── radio_panel.py       # Radio communications
└── aircraft_panel.py    # Aircraft information
```

**To modify UI:**
1. Edit files in `src/ui/`
2. Qt Designer can be used for layouts
3. Simulation logic remains in `src/core/` and `src/rendering/`

## 🎓 Learning Resources

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [Qt Widgets Overview](https://doc.qt.io/qt-6/qtwidgets-index.html)
- [Pygame in Qt Tutorial](https://stackoverflow.com/questions/tagged/pygame+pyside6)

## 🙏 Credits

- **Simulation Engine:** Original AsdeSim Pygame code
- **UI Framework:** PySide6 (Qt for Python)
- **Integration:** Custom embedding layer

---

**Enjoy the new professional interface! 🎮✈️**
