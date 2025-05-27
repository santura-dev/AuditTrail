from django.core.management.base import BaseCommand
from logger.mongo import get_mongo_collection
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Archives logs older than a specified number of days to logs_archive collection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to consider for archiving (default: 30)',
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        self.stdout.write(f"Archiving logs older than {cutoff_date}")

        try:
            # Get MongoDB collections
            logs_collection = get_mongo_collection('logs_collection')
            archive_collection = get_mongo_collection('logs_archive')

            # Find logs to archive
            query = {'timestamp': {'$lt': cutoff_date}}
            logs_to_archive = logs_collection.find(query)
            logs_count = logs_collection.count_documents(query)

            if logs_count == 0:
                self.stdout.write("No logs to archive.")
                logger.info("No logs to archive.")
                return

            # Archive logs
            for log in logs_to_archive:
                archive_collection.insert_one(log)
                logs_collection.delete_one({'_id': log['_id']})

            self.stdout.write(self.style.SUCCESS(f"Successfully archived {logs_count} logs."))
            logger.info(f"Archived {logs_count} logs older than {cutoff_date}.")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during archival: {str(e)}"))
            logger.error(f"Error during log archival: {str(e)}")
            raise