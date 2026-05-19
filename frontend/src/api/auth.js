// Placeholder auth API — no backend auth yet
export async function login(email, _password) {
  return { user: { email, name: email.split('@')[0] }, token: 'mock' }
}

export async function signup(name, email, _password) {
  return { user: { email, name }, token: 'mock' }
}
