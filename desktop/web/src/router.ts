import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";
import DataView from "./views/DataView.vue";
import DataSourcesView from "./views/DataSourcesView.vue";
import F10View from "./views/F10View.vue";
import IndustryView from "./views/IndustryView.vue";
import LogsView from "./views/LogsView.vue";
import MarketView from "./views/MarketView.vue";
import StrategyView from "./views/StrategyView.vue";
import StatsView from "./views/StatsView.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HomeView },
    { path: "/market/", component: MarketView },
    { path: "/data/", component: DataView },
    { path: "/data-sources/", component: DataSourcesView },
    { path: "/strategy/", component: StrategyView },
    { path: "/stats/", component: StatsView },
    { path: "/f10/", component: F10View },
    { path: "/f10/company/:instrumentKey", component: F10View, props: true },
    { path: "/industry/", component: IndustryView },
    { path: "/logs/", component: LogsView },
    { path: "/industry-v2/", redirect: "/industry/" },
  ],
});
