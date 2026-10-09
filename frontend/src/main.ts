import { createApp } from 'vue'
import UIkit from 'uikit'
import Icons from 'uikit/dist/js/uikit-icons'
import './style.css'
import App from './App.vue'

UIkit.use(Icons)

createApp(App).mount('#app')
