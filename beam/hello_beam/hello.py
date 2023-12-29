import apache_beam as beam 

p = beam.Pipeline()

p | beam.Create(["Hello", "World"]) | beam.Map(print)

p.run()