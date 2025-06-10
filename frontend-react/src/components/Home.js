import { Link } from "react-router-dom";

function Home() {
    return (
      <div>
        <h1>Welcome to My Recharts SPA</h1>
        <Link to="/charts">Charts</Link>
      </div>
    );
  }
  
  export default Home;