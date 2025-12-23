# Fuzzbin UI Design System
## Neo-MTV Maximalism

### Design Philosophy

**Concept**: "Channel Surfing in 2025"
The interface is organized into color-coded "channels" - each major section has its own vibrant identity while maintaining cohesion through shared geometric language and bold typography.

**Core Principles**:
1. **Bold but Organized**: Maximum visual energy within structured layouts
2. **Color as Navigation**: Each section has a signature color that aids wayfinding
3. **Tactile Depth**: Heavy shadows and layering create tangible UI elements
4. **Musical Rhythm**: Animations have timing and bounce like music beats
5. **Celebration of Content**: Video thumbnails are heroes, not afterthoughts

---

## Color System

### Channel Colors (Primary Zones)
```css
--channel-library: #00F0FF;    /* Electric Cyan - Video Library */
--channel-import: #FF006E;     /* Hot Magenta - YouTube Import */
--channel-player: #FFD60A;     /* Laser Yellow - Video Player */
--channel-manage: #39FF14;     /* Neon Green - Collections/Tags */
--channel-system: #9D4EDD;     /* Purple - Admin/Settings */
```

### Base Palette
```css
/* Backgrounds */
--bg-base: #0A0014;           /* Deep purple-black */
--bg-surface: #1A0F2E;        /* Dark purple - cards */
--bg-surface-light: #2D1B4E;  /* Purple-gray - elevated */
--bg-surface-hover: #3D2B5E;  /* Lighter hover state */

/* Text */
--text-primary: #F8F8FF;      /* Off-white */
--text-secondary: #B8A8D8;    /* Light purple-gray */
--text-tertiary: #8B7AA8;     /* Muted purple */

/* Semantic */
--success: #39FF14;           /* Neon green */
--warning: #FFD60A;           /* Laser yellow */
--error: #FF006E;             /* Hot magenta */
--info: #00F0FF;              /* Electric cyan */

/* Gradients */
--gradient-mesh: radial-gradient(at 0% 0%, rgba(157, 78, 221, 0.3) 0px, transparent 50%),
                 radial-gradient(at 100% 0%, rgba(0, 240, 255, 0.2) 0px, transparent 50%),
                 radial-gradient(at 100% 100%, rgba(255, 0, 110, 0.25) 0px, transparent 50%),
                 radial-gradient(at 0% 100%, rgba(255, 214, 10, 0.2) 0px, transparent 50%);
```

---

## Typography

### Font Families
```css
/* Display - Headers, Section Titles */
--font-display: 'Barlow Condensed', 'Impact', sans-serif;
/* Weight: 700 (Bold), 800 (Extra Bold) */

/* Body - Content, Paragraphs */
--font-body: 'Outfit', 'Segoe UI', sans-serif;
/* Weight: 400 (Regular), 500 (Medium), 600 (Semi Bold) */

/* UI - Labels, Buttons, Badges */
--font-ui: 'Barlow', 'Arial Narrow', sans-serif;
/* Weight: 600 (Semi Bold), 700 (Bold) */
```

### Type Scale
```css
--text-xs: 0.75rem;     /* 12px - Small labels */
--text-sm: 0.875rem;    /* 14px - Body small */
--text-base: 1rem;      /* 16px - Body */
--text-lg: 1.125rem;    /* 18px - Large body */
--text-xl: 1.5rem;      /* 24px - Subheadings */
--text-2xl: 2rem;       /* 32px - Section headers */
--text-3xl: 3rem;       /* 48px - Page headers */
--text-4xl: 4rem;       /* 64px - Hero */
```

### Typography Styles
```css
.display-hero {
  font-family: var(--font-display);
  font-size: var(--text-4xl);
  font-weight: 800;
  line-height: 0.95;
  letter-spacing: -0.02em;
  text-transform: uppercase;
}

.display-section {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}

.body-large {
  font-family: var(--font-body);
  font-size: var(--text-lg);
  font-weight: 400;
  line-height: 1.6;
}

.label-ui {
  font-family: var(--font-ui);
  font-size: var(--text-sm);
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
```

---

## Spacing & Layout

### Spacing Scale
```css
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-5: 1.5rem;    /* 24px */
--space-6: 2rem;      /* 32px */
--space-8: 3rem;      /* 48px */
--space-10: 4rem;     /* 64px */
--space-12: 6rem;     /* 96px */
```

### Border Radius
```css
--radius-sm: 4px;     /* Subtle rounding */
--radius-md: 8px;     /* Standard cards */
--radius-lg: 16px;    /* Chunky elements */
--radius-xl: 24px;    /* Hero sections */
--radius-full: 9999px; /* Pills, badges */
```

### Shadows (Chunky Depth)
```css
--shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.4),
             0 1px 2px rgba(0, 0, 0, 0.3);

--shadow-md: 0 4px 8px rgba(0, 0, 0, 0.5),
             0 2px 4px rgba(0, 0, 0, 0.4);

--shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.6),
             0 4px 8px rgba(0, 0, 0, 0.5);

--shadow-xl: 0 16px 32px rgba(0, 0, 0, 0.7),
             0 8px 16px rgba(0, 0, 0, 0.6);

/* Colored glow shadows */
--shadow-glow-cyan: 0 0 20px rgba(0, 240, 255, 0.5),
                    0 0 40px rgba(0, 240, 255, 0.2);

--shadow-glow-magenta: 0 0 20px rgba(255, 0, 110, 0.5),
                       0 0 40px rgba(255, 0, 110, 0.2);

--shadow-glow-yellow: 0 0 20px rgba(255, 214, 10, 0.5),
                      0 0 40px rgba(255, 214, 10, 0.2);
```

---

## Component Patterns

### Buttons

**Primary (Channel-Colored)**
```css
.btn-primary {
  padding: var(--space-3) var(--space-6);
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: var(--text-base);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border: 3px solid currentColor;
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  color: var(--channel-library);
  box-shadow: var(--shadow-lg);
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.btn-primary:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--shadow-xl), var(--shadow-glow-cyan);
}

.btn-primary:active {
  transform: translateY(0) scale(0.98);
}
```

**Ghost (Outline)**
```css
.btn-ghost {
  padding: var(--space-3) var(--space-5);
  background: transparent;
  border: 2px solid var(--text-secondary);
  color: var(--text-primary);
  border-radius: var(--radius-md);
}

.btn-ghost:hover {
  border-color: var(--channel-library);
  color: var(--channel-library);
  background: rgba(0, 240, 255, 0.1);
}
```

### Cards

**Video Card (Library Grid)**
```css
.video-card {
  background: var(--bg-surface);
  border: 2px solid var(--bg-surface-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-md);
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.video-card:hover {
  transform: translateY(-4px) rotate(-1deg);
  border-color: var(--channel-library);
  box-shadow: var(--shadow-xl), var(--shadow-glow-cyan);
}

.video-card-thumbnail {
  aspect-ratio: 16/9;
  background: var(--bg-surface-light);
  position: relative;
  overflow: hidden;
}

.video-card-thumbnail::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 0%, rgba(10, 0, 20, 0.8) 100%);
  opacity: 0;
  transition: opacity 0.3s;
}

.video-card:hover .video-card-thumbnail::after {
  opacity: 1;
}
```

### Badges (Tags/Status)

**Sticker-style badges**
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  font-family: var(--font-ui);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border: 2px solid currentColor;
  border-radius: var(--radius-full);
  background: var(--bg-surface);
  color: var(--channel-library);
  box-shadow: var(--shadow-sm);
  white-space: nowrap;
  transform: rotate(-2deg);
}

.badge:nth-child(even) {
  transform: rotate(2deg);
}
```

### Navigation Sidebar

**Chunky, channel-coded navigation**
```css
.sidebar {
  width: 280px;
  background: var(--bg-surface);
  border-right: 3px solid var(--bg-surface-light);
  padding: var(--space-6);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  margin-bottom: var(--space-2);
  border-radius: var(--radius-lg);
  border: 2px solid transparent;
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--text-secondary);
  transition: all 0.2s;
  position: relative;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 0;
  background: var(--channel-library);
  border-radius: var(--radius-full);
  transition: height 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.nav-item:hover,
.nav-item.active {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
  border-color: var(--channel-library);
}

.nav-item:hover::before,
.nav-item.active::before {
  height: 32px;
}
```

---

## Animation System

### Timing Functions
```css
--ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
--ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
--ease-sharp: cubic-bezier(0.4, 0, 1, 1);
```

### Keyframe Animations

**Stagger Fade In (Page Load)**
```css
@keyframes stagger-fade-in {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stagger-item {
  animation: stagger-fade-in 0.6s var(--ease-bounce) both;
}

.stagger-item:nth-child(1) { animation-delay: 0.05s; }
.stagger-item:nth-child(2) { animation-delay: 0.1s; }
.stagger-item:nth-child(3) { animation-delay: 0.15s; }
/* ... etc */
```

**Pulse (Progress Indicators)**
```css
@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(0, 240, 255, 0.7);
  }
  50% {
    box-shadow: 0 0 20px 10px rgba(0, 240, 255, 0);
  }
}

.progress-pulse {
  animation: pulse-glow 2s infinite;
}
```

**Rotate Bounce (Loading)**
```css
@keyframes rotate-bounce {
  0% { transform: rotate(0deg) scale(1); }
  50% { transform: rotate(180deg) scale(1.1); }
  100% { transform: rotate(360deg) scale(1); }
}

.loading-spinner {
  animation: rotate-bounce 1.5s var(--ease-bounce) infinite;
}
```

---

## Layout Patterns

### Main Application Shell
```
┌─────────────────────────────────────────┐
│  [LOGO] FUZZBIN          [USER] [SEARCH]│ ← Header (60px, gradient bg)
├───────┬─────────────────────────────────┤
│       │                                 │
│  NAV  │                                 │
│       │      MAIN CONTENT AREA          │
│  280px│      (Dynamic routing)          │
│       │                                 │
│       │                                 │
└───────┴─────────────────────────────────┘
```

### Video Library Grid
```css
.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-6);
  padding: var(--space-6);
}

@media (min-width: 1536px) {
  .video-grid {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
}
```

### Asymmetric Split (Import/Search)
```css
.split-layout {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: var(--space-8);
  padding: var(--space-6);
}

@media (max-width: 1024px) {
  .split-layout {
    grid-template-columns: 1fr;
  }
}
```

---

## Channel Zone Styling

Each major section gets a signature color applied to:
- Active nav item accent
- Primary buttons
- Section headers
- Glow effects
- Border highlights

**Example - Library Channel (Cyan)**
```css
.channel-library {
  --channel-color: var(--channel-library);
  --channel-glow: var(--shadow-glow-cyan);
}

.channel-library .section-header {
  color: var(--channel-color);
  text-shadow: 0 0 20px rgba(0, 240, 255, 0.5);
}
```

---

## Responsive Breakpoints

```css
/* Mobile First */
--bp-sm: 640px;   /* Small tablets */
--bp-md: 768px;   /* Tablets */
--bp-lg: 1024px;  /* Small laptops */
--bp-xl: 1280px;  /* Desktops */
--bp-2xl: 1536px; /* Large desktops */
```

**Mobile Adaptations**:
- Sidebar collapses to hamburger menu < 1024px
- Video grid: 1 column (mobile) → 2 columns (tablet) → 3+ columns (desktop)
- Player switches to full-screen modal on mobile
- Search filters collapse into drawer

---

## Accessibility

- All interactive elements meet WCAG AA contrast (4.5:1 minimum)
- Focus indicators use 3px solid outline with channel color
- Animations respect `prefers-reduced-motion`
- Color is never the only indicator (icons, labels accompany)
- Skip navigation link for keyboard users

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Implementation Notes

**CSS Architecture**:
- CSS Modules or Styled Components for component scoping
- Global design tokens in `:root` or theme context
- Utility classes for common patterns (spacing, typography)

**Performance**:
- Lazy load images with blur placeholders
- Virtualize long video lists (react-window)
- Debounce search input
- Optimize animations with `transform` and `opacity` only

**Dark Mode**:
- Default is dark (MTV nighttime energy)
- Optional light mode inverts: lighter purples, darker accents
