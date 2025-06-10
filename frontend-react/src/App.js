import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Charts from './components/Charts';

function App() {
  return (
    <Charts />
/*     <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/charts" element={<Chart />} />
      </Routes>
    </BrowserRouter> */
  );
}

export default App;