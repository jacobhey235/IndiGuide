import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.indiguide.app',
  appName: 'IndiGuide',
  webDir: 'dist',
  server: {
    url: 'https://indiguide.onrender.com',
    cleartext: false,
  },
  android: {
    backgroundColor: '#111827',
  },
}

export default config
