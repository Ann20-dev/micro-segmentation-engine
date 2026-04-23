import React, { useState } from 'react';

function Login({ onLogin, pendingOtp, setPendingOtp }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [message, setMessage] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    const response = await fetch('http://localhost:5000/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (data.status === 'otp_required') {
      setPendingOtp(true);
      setMessage(data.message);
    } else {
      setMessage(data.message);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    const response = await fetch('http://localhost:5000/api/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ otp_code: otp }),
    });
    const data = await response.json();
    if (data.status === 'success') {
      onLogin(data.user, data.role, data.zone);
    } else {
      setMessage(data.message);
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '50px auto', padding: '20px', border: '1px solid #ccc' }}>
      <h1>Micro-Segmentation Engine</h1>
      {message && <p>{message}</p>}
      {!pendingOtp ? (
        <form onSubmit={handleLogin}>
          <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button type="submit">Login</button>
        </form>
      ) : (
        <form onSubmit={handleVerifyOtp}>
          <input type="text" placeholder="OTP Code" value={otp} onChange={(e) => setOtp(e.target.value)} required />
          <button type="submit">Verify OTP</button>
        </form>
      )}
      <div>
        <h2>Demo Users</h2>
        <p>normal_user / user123</p>
        <p>finance_user / finance123</p>
        <p>admin_user / admin123</p>
      </div>
    </div>
  );
}

export default Login;