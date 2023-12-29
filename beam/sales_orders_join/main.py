import apache_beam as beam

p = beam.Pipeline()

sales = (p | beam.io.ReadFromText("C:/Users/darsh/OneDrive/Desktop/projects/python-projects/beam/sales_orders_join/data/sales.csv",
                         skip_header_lines=True) 
            | beam.Map(lambda x: x.split(','))
            | beam.GroupBy(lambda r: r[2])
            | beam.Map(print)
        )


orders = (p | beam.io.ReadFromText("C:/Users/darsh/OneDrive/Desktop/projects/python-projects/beam/sales_orders_join/data/orders.csv",
                         skip_header_lines=True) | beam.Map(lambda x: x.split(','))
)

p.run()

