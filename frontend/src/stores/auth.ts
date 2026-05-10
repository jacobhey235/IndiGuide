import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  const isAuthenticated = () => !!token.value

  async function login(email: string, password: string) {
    const { data } = await client.post<{ access_token: string }>('/auth/login', { email, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchMe()
  }

  async function register(email: string, username: string, password: string) {
    await client.post('/auth/register', { email, username, password })
    await login(email, password)
  }

  async function fetchMe() {
    if (!token.value) return
    const { data } = await client.get<User>('/auth/me')
    user.value = data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, isAuthenticated, login, register, fetchMe, logout }
})
