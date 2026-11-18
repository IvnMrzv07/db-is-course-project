"""Explicit operator recovery for completion messages; bounded and confirm-before-ack."""
import asyncio
import argparse
import json
from ingestion_service.infrastructure.messaging.runtime_broker import Broker

async def redrive(name,limit):
    broker=await Broker().connect()
    try:
        queue=await broker.channel.get_queue(name+'.failed')
        moved=0
        for _ in range(limit):
            message=await queue.get(fail=False)
            if message is None:break
            try:
                await broker.publish(name,json.loads(message.body))
                await message.ack()
                moved+=1
            except Exception:
                await message.nack(requeue=True)
                raise
        print(f'Redriven {moved} messages')
    finally:await broker.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('queue',choices=['corpus.completed'])
    parser.add_argument('--limit',type=int,default=100)
    args=parser.parse_args()
    if not 1<=args.limit<=10000:parser.error('limit must be 1..10000')
    asyncio.run(redrive(args.queue,args.limit))
