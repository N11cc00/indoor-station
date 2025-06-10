import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

const data = [
  { name: 'Jan', value: 400 },
  { name: 'Feb', value: 300 },
  { name: 'Mar', value: 600 },
  // Add more data
];

function Charts() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('http://nico-behrens.de:5000/sensor')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then((result) => setData(result))
      .catch((error) => console.error('Error fetching data:', error));
  }, []); // Empty dependency array for one-time fetch on mount

  return (
    <div>
      <h2>Sensor Data</h2>
      {data.length > 0 ? (
        <LineChart width={600} height={300} data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="value" stroke="#8884d8" />
        </LineChart>
      ) : (
        <p>Loading data...</p>
      )}
    </div>
  );
}

export default Charts;