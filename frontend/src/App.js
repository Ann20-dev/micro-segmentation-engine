import React, { useState } from 'react';
import Login from './Login';
import Dashboard from './Dashboard';
import Chat from './Chat';

function App() {
  const [user, setUser] = useState(null);
  const [pendingOtp, setPendingOtp] = useState(false);

  const handleLogin = (username, role, zone) => {
    setUser({ username, role, zone });
    setPendingOtp(false);
  };

  const handleLogout = () => {
    setUser(null);
    setPendingOtp(false);
  };

  if (!user) {
    return <Login onLogin={handleLogin} pendingOtp={pendingOtp} setPendingOtp={setPendingOtp} />;
  }

  return (
    <div>
      <Dashboard user={user} onLogout={handleLogout} />
      <Chat user={user} />
    </div>
  );
}

export default App;