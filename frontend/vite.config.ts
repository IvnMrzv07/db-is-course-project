import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{proxy:{'/api/v1/replays':'http://127.0.0.1:8001','/api/v1/snapshots':'http://127.0.0.1:8001','/api/v1':'http://127.0.0.1:8000'}}});
