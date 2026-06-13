import type { CapacitorConfig } from '@capacitor/cli';

// Optional native shell config. Not wired into the web build — it only matters
// once you add Capacitor (see README "Native app (optional)"). Kept here so the
// project is ready to become an Android/iOS app without restructuring.
const config: CapacitorConfig = {
  appId: 'app.viralcut.ai',
  appName: 'ViralCut AI',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
};

export default config;
