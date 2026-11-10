# billing database after the AWS move (cutover 2023-02-18)
resource "aws_db_instance" "billing_prod" {
  identifier              = "billing-prod"
  engine                  = "postgres"
  engine_version          = "14.6"
  instance_class          = "db.r6g.xlarge"
  allocated_storage       = 500
  multi_az                = true
  username                = "billing_admin"
  password                = var.billing_db_password   # REDACTED - stored in SSM /prod/billing/db
  backup_retention_period = 14
  deletion_protection     = true
  tags = { owner = "cmacleod", cost_center = "ENG-PLAT" }
}
