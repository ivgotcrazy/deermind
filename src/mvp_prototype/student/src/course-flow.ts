import { reactive } from 'vue';
import { readFlow, subscribeFlow } from '../../shared/learning-flow';
export const courseFlow=reactive(readFlow());
subscribeFlow(state=>Object.assign(courseFlow,state));
