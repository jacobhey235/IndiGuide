import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'
import RouteView from '@/views/RouteView.vue'
import WalkView from '@/views/WalkView.vue'
import ProfileView from '@/views/ProfileView.vue'
import ExploreRouteView from '@/views/ExploreRouteView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/explore/:id', name: 'explore-route', component: ExploreRouteView, meta: { requiresAuth: true } },
    { path: '/routes/:id', name: 'route', component: RouteView },
    { path: '/routes/:id/walk', name: 'walk', component: WalkView, meta: { requiresAuth: true } },
    { path: '/profile', name: 'profile', component: ProfileView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated()) {
    return { name: 'home' }
  }
})

export default router
