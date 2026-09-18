"""Bounded, graph-free preparation with an ordered consumer."""
import time
from concurrent.futures import ThreadPoolExecutor

class SegmentPrefetch:
    def __init__(self, plan, prepare, ahead=2):
        self.plan=plan;self.prepare=prepare;self.ahead=ahead
        self.pool=ThreadPoolExecutor(max_workers=ahead+1)
        self.futures={};self.admitted={}
    def _work(self, index):
        start=time.perf_counter()
        result=self.prepare(self.plan[index-1],index)
        result['prepared_perf']=time.perf_counter()
        result['preparation_work_ms']=(result['prepared_perf']-start)*1000
        return result
    def get(self,index):
        for i in range(index,min(len(self.plan),index+self.ahead)+1):
            if i not in self.futures:
                self.admitted[i]=time.perf_counter()
                self.futures[i]=self.pool.submit(self._work,i)
        started=time.perf_counter()
        result=self.futures.pop(index).result()
        now=time.perf_counter()
        result['pipeline_timing']={
            'admitted_perf':self.admitted.pop(index),'prepared_perf':result['prepared_perf'],
            'ordered_start_perf':now,'consumer_wait_ms':(now-started)*1000,
            'ready_to_ordered_ms':max(0,(now-result['prepared_perf'])*1000),
            'preparation_work_ms':result['preparation_work_ms'],'lookahead_segments':self.ahead}
        return result
    def close(self):self.pool.shutdown(wait=True,cancel_futures=True)
