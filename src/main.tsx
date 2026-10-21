import { createRoot } from 'react-dom/client';
import 'maplibre-gl/dist/maplibre-gl.css';
import 'uplot/dist/uPlot.min.css';
import './styles/tokens.css';
import './styles/global.css';
import { App } from './App';

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Root element #root is missing');

createRoot(rootElement).render(<App />);
