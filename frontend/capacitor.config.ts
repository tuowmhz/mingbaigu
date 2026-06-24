import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.mingbaigu.app',
  appName: '明白股',
  webDir: 'dist',
  backgroundColor: '#0b0f1d',
  ios: {
    contentInset: 'automatic',
  },
  android: {
    allowMixedContent: false,
  },
}

export default config
