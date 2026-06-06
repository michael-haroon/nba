import json
import boto3
from datetime import datetime
from nba_api.stats.endpoints import BoxScoreSummaryV3

# --- Configuration ---
BUCKET_NAME = "nba-265753586044-us-east-1-an"
S3_PREFIX = "api_data/boxscore_summary_"

s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Fetches NBA API data and saves the raw JSON payload to S3.
    Expects 'game_id' in the invocation event.
    """
    game_id = event.get('game_id', '0022500142') # Default for testing
    
    try:
        # 1. Fetch data from NBA API
        summary = BoxScoreSummaryV3(game_id=game_id, timeout=15)
        
        # 2. Extract raw JSON payload directly from the underlying response engine
        raw_json_str = summary.nba_response.get_json()
        
        if not raw_json_str:
            return {'statusCode': 404, 'body': 'No data payload returned for game_id'}

        # 3. Format the file name and switch file extension to .json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"{S3_PREFIX}{game_id}_{timestamp}.json"
        
        # 4. Upload raw string payload straight to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=raw_json_str,
            ContentType="application/json"
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f"Successfully saved to {s3_key}"})
        }

    except Exception as e:
        print(f"Error processing game {game_id}: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}