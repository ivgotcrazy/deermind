import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import App from './App.vue';
import './style.css';
const router=createRouter({history:createWebHashHistory(),routes:[{path:'/:page?',component:{render:()=>null}}],scrollBehavior:(_to,_from,saved)=>saved||{top:0}});
// Keep legacy chapter bookmarks; homepage and chapter assessment have separate routes.
router.beforeEach(to=>{
 const role=new URLSearchParams(location.search).get('role');
 if(role==='parent'||role==='admin')return;
 if(to.path==='/')return {path:to.query.chapter?'/status':'/home',query:to.query,replace:true};
 if(to.path==='/home'&&to.query.chapter)return {path:'/status',query:to.query,replace:true};
});
createApp(App).use(router).mount('#app');
