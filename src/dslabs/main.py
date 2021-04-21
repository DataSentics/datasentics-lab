
from dslabs.dbpathlib.dbpath import DBPath

if __name__ == '__main__':
    
    print('hello')
    
    from pyspark.sql import SparkSession
    
    spark  = SparkSession.builder.getOrCreate()
    DBPath.set_spark_session(spark)
    
    path = DBPath('file:/')
    path.ls()
    