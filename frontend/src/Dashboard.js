import React, { useEffect, useState } from 'react';

function Dashboard({ user, onLogout }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch('http://localhost:5000/api/dashboard')
      .then(res => res.json())
      .then(setData);
  }, []);

  const handleLogout = async () => {
    await fetch('http://localhost:5000/api/logout', { method: 'POST' });
    onLogout();
  };

  if (!data) return <div>Loading...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Welcome, {user.username}</h1>
      <p>Role: {user.role} | Zone: {user.zone}</p>
      <button onClick={handleLogout}>Logout</button>
      <h2>SMS Alerts</h2>
      <ul>
        {data.alerts.map((alert, i) => (
          <li key={i}>{alert.category}: {alert.message}</li>
        ))}
      </ul>
    </div>
  );
}

export default Dashboard;