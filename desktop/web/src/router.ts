import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";
import DataView from "./views/DataView.vue";
import F10View from "./views/F10View.vue";
import IndustryView from "./views/IndustryView.vue";
import LogsView from "./views/LogsView.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HomeView },
    { path: "/data/", component: DataView },
    { path: "/f10/", component: F10View },
    { path: "/f10/company/:instrumentKey", component: F10View, props: true },
    { path: "/industry/", component: IndustryView },
    { path: "/logs/", component: LogsView },
    { path: "/industry-v2/", redirect: "/industry/" },
  ],
});
