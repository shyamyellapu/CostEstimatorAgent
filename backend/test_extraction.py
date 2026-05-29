import sys, asyncio, os
sys.path.insert(0, r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\backend')
os.chdir(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent')

from app.services.rfq_extractor import extract_from_attachment

filepath = r'./storage\rfq_uploads\77f69da5-1823-4d2c-b6a9-105b8ff09ca1\bd61a4a0-1204-42ce-b045-4e237b014e48_ADI60049-ST-001.pdf'

async def main():
    try:
        result = await extract_from_attachment(
            filepath=filepath,
            filename='ADI60049-ST-001.pdf',
            file_category='pdf',
            document_type='other',
        )
        print('SUCCESS')
        print('line_items:', len(result.get('line_items', [])))
        print('metadata:', result.get('metadata', {}))
        print('source_stage:', result.get('source_stage'))
        if result.get('line_items'):
            print('First item:', result['line_items'][0])
        if result.get('error'):
            print('ERROR in result:', result['error'])
    except Exception as e:
        import traceback
        print('EXCEPTION:', e)
        traceback.print_exc()

asyncio.run(main())
